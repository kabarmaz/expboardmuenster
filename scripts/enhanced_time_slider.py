#!/usr/bin/env python3
"""
Enhanced Time-Slider Map for Urban Expansion with Predictions
Shows historical data from 2015-2025 and predictions for 2026-2030
"""

import geopandas as gpd
import pandas as pd
import numpy as np
import folium
from folium import plugins
from pathlib import Path
import json
import glob

# Setup
output_dir = Path("output/interactive")
output_dir.mkdir(parents=True, exist_ok=True)

# =============================================================================
# LOAD AND PROCESS ALL BUILDING DATA
# =============================================================================

print("Loading building data from 2015-2025...")

# Load the prediction data
print("Loading prediction areas...")
pred_grid = gpd.read_file("output/growth_prediction/predicted_growth_areas.geojson")
pred_grid = pred_grid.to_crs(epsg=4326)

# Load forecasts for prediction values
forecasts = pd.read_csv("output/forecasting/forecasts.csv")
print(f"Forecasts:\n{forecasts}")

# Load building growth summary for the timeline
growth_summary = pd.read_csv("output/building_growth_summary.csv")
print(f"\nBuilding growth summary: {len(growth_summary)} periods")

# Get all period dates from the summary
period_dates = growth_summary['period_end'].tolist()
new_buildings_per_period = dict(zip(growth_summary['period_end'], growth_summary['new_buildings']))

print(f"Periods from {period_dates[0]} to {period_dates[-1]}")

# Load base grid (for geometry)
try:
    grid = gpd.read_file("output/spatial_stats/grid_with_direction.geojson")
    grid = grid.to_crs(epsg=4326)
    print(f"Loaded grid with {len(grid)} cells")
except:
    grid = gpd.read_file("output/grid_new_buildings.geojson")
    grid = grid.to_crs(epsg=4326)
    print(f"Loaded grid with {len(grid)} cells")

# Get center coordinates
center_lat = grid.geometry.centroid.y.mean()
center_lon = grid.geometry.centroid.x.mean()
print(f"Map center: {center_lat:.4f}, {center_lon:.4f}")

# =============================================================================
# COLOR SCHEMES
# =============================================================================

def get_historical_color(value, max_val):
    """Yellow-Orange-Red for historical data"""
    if value == 0:
        return '#f0f0f0'
    ratio = min(value / max_val, 1)
    r = 255
    g = int(255 * (1 - ratio))
    b = 0
    return f'#{r:02x}{g:02x}{b:02x}'

# Different color schemes for prediction years
PREDICTION_COLORS = {
    2026: {'base': '#3498db', 'name': 'Blue'},      # Blue
    2027: {'base': '#9b59b6', 'name': 'Purple'},    # Purple  
    2028: {'base': '#1abc9c', 'name': 'Teal'},      # Teal
    2029: {'base': '#e74c3c', 'name': 'Red'},       # Red
    2030: {'base': '#f39c12', 'name': 'Orange'},    # Orange
}

def get_prediction_color(year, dev_potential):
    """Get color for prediction based on year and development potential"""
    if year not in PREDICTION_COLORS:
        return '#888888'
    
    base_color = PREDICTION_COLORS[year]['base']
    # Parse hex color
    r = int(base_color[1:3], 16)
    g = int(base_color[3:5], 16)
    b = int(base_color[5:7], 16)
    
    # Adjust intensity based on development potential
    intensity = 0.3 + 0.7 * dev_potential  # Range from 0.3 to 1.0
    r = int(r * intensity)
    g = int(g * intensity)
    b = int(b * intensity)
    
    return f'#{r:02x}{g:02x}{b:02x}'

# =============================================================================
# CREATE THE TIME SLIDER MAP
# =============================================================================

print("\n" + "=" * 60)
print("CREATING ENHANCED TIME-SLIDER MAP")
print("=" * 60)

# Create base map
m = folium.Map(location=[center_lat, center_lon], zoom_start=11, tiles='cartodbpositron')

# Prepare features for all time periods
all_features = []

# Calculate max value for color scaling
# Use the total buildings field if available, or estimate from summary
max_new_per_cell = 50  # Reasonable estimate for cell-level max

# Get period columns from grid if available
period_cols = [c for c in grid.columns if c.startswith('new_')]
period_cols = sorted(period_cols)

print(f"Grid has {len(period_cols)} period columns: {period_cols}")

# =============================================================================
# HISTORICAL DATA (2015-2025)
# =============================================================================

print("\nProcessing historical data...")

# For each historical period, create features
# We'll distribute the building growth across high-potential areas

# Get cells with any existing growth data
if 'total_new' in grid.columns:
    growth_cells = grid[grid['total_new'] > 0].copy()
else:
    # Sum all period columns
    grid['total_new'] = grid[period_cols].sum(axis=1) if period_cols else 0
    growth_cells = grid[grid['total_new'] > 0].copy()

print(f"Found {len(growth_cells)} cells with growth")

# For periods we have detailed data, use it
for period_col in period_cols:
    period_date = period_col.replace('new_', '')
    
    for idx, row in grid.iterrows():
        value = row[period_col] if period_col in row.index else 0
        if value > 0:
            feat = {
                'type': 'Feature',
                'geometry': row['geometry'].__geo_interface__,
                'properties': {
                    'time': period_date + 'T00:00:00',
                    'new_buildings': int(value),
                    'type': 'historical',
                    'style': {
                        'fillColor': get_historical_color(value, max_new_per_cell),
                        'color': 'gray',
                        'weight': 0.5,
                        'fillOpacity': 0.7
                    }
                }
            }
            all_features.append(feat)
    
    print(f"  {period_date}: added features")

# For periods we DON'T have detailed grid data, simulate using growth patterns
# Get periods that aren't in the grid columns
grid_periods = [c.replace('new_', '') for c in period_cols]
missing_periods = [p for p in period_dates if p not in grid_periods]

print(f"\nSimulating {len(missing_periods)} missing historical periods...")

# Use proportion from existing growth patterns to distribute
if len(growth_cells) > 0:
    total_existing = growth_cells['total_new'].sum()
    cell_proportions = growth_cells['total_new'] / total_existing if total_existing > 0 else 0
    
    for period in missing_periods:
        total_new = new_buildings_per_period.get(period, 0)
        
        # Distribute proportionally across growth cells
        for idx, row in growth_cells.iterrows():
            proportion = row['total_new'] / total_existing if total_existing > 0 else 0
            estimated_new = total_new * proportion
            
            if estimated_new > 0.5:  # Only add if significant
                feat = {
                    'type': 'Feature',
                    'geometry': row['geometry'].__geo_interface__,
                    'properties': {
                        'time': period + 'T00:00:00',
                        'new_buildings': int(estimated_new),
                        'type': 'historical_estimated',
                        'style': {
                            'fillColor': get_historical_color(estimated_new, max_new_per_cell),
                            'color': 'gray',
                            'weight': 0.5,
                            'fillOpacity': 0.6
                        }
                    }
                }
                all_features.append(feat)
        
        print(f"  {period}: estimated {total_new} buildings distributed")

# =============================================================================
# PREDICTION DATA (2026-2030)
# =============================================================================

print("\nProcessing prediction data...")

# Get high-potential cells for predictions
if 'dev_potential' in pred_grid.columns:
    high_potential = pred_grid[pred_grid['dev_potential'] > 0.3].copy()
else:
    high_potential = pred_grid.copy()

print(f"Using {len(high_potential)} cells for predictions")

# Create prediction features for each year
for year in range(2026, 2031):
    # Use forecast ensemble values
    year_forecast = forecasts[forecasts['date'].str.startswith(str(year))]
    avg_new = year_forecast['ensemble'].mean() if len(year_forecast) > 0 else 400
    
    # Count for distribution
    added = 0
    
    for idx, row in high_potential.iterrows():
        dev_potential = row.get('dev_potential', 0.5)
        
        # Only show cells above threshold that decreases each year
        # (stronger predictions are more confident)
        threshold = 0.3 + (year - 2026) * 0.05  # 0.3, 0.35, 0.4, 0.45, 0.5
        
        if dev_potential > threshold:
            # Estimate building count based on potential
            estimated_new = int(avg_new * dev_potential / len(high_potential) * 5)
            
            feat = {
                'type': 'Feature',
                'geometry': row['geometry'].__geo_interface__,
                'properties': {
                    'time': f'{year}-01-01T00:00:00',
                    'predicted_buildings': estimated_new,
                    'dev_potential': float(dev_potential),
                    'type': 'prediction',
                    'year': year,
                    'style': {
                        'fillColor': get_prediction_color(year, dev_potential),
                        'color': PREDICTION_COLORS[year]['base'],
                        'weight': 1,
                        'fillOpacity': 0.7
                    }
                }
            }
            all_features.append(feat)
            added += 1
    
    print(f"  {year}: {added} prediction cells ({PREDICTION_COLORS[year]['name']})")

# =============================================================================
# BUILD THE MAP
# =============================================================================

print(f"\nTotal features: {len(all_features)}")

geojson_data = {
    'type': 'FeatureCollection',
    'features': all_features
}

# Add TimestampedGeoJson
plugins.TimestampedGeoJson(
    geojson_data,
    period='P6M',  # 6 months per step
    add_last_point=True,
    auto_play=False,
    loop=False,
    max_speed=1,
    loop_button=True,
    date_options='YYYY-MM-DD',
    time_slider_drag_update=True,
    transition_time=200
).add_to(m)

# Add city center marker
folium.Marker(
    [51.9625, 7.6261],
    popup='Münster City Center',
    icon=folium.Icon(color='blue', icon='star')
).add_to(m)

# =============================================================================
# ADD LEGEND
# =============================================================================

legend_html = '''
<div style="position: fixed; bottom: 50px; right: 50px; z-index: 1000; 
            background-color: white; padding: 15px; border: 2px solid gray;
            border-radius: 5px; font-size: 12px; max-width: 200px;">
    <b>Urban Expansion Timeline</b><br><br>
    <b>Historical (2015-2025):</b><br>
    <i style="background: #ffff00; width: 18px; height: 18px; display: inline-block; margin-right: 5px;"></i> Low growth<br>
    <i style="background: #ff8000; width: 18px; height: 18px; display: inline-block; margin-right: 5px;"></i> Medium growth<br>
    <i style="background: #ff0000; width: 18px; height: 18px; display: inline-block; margin-right: 5px;"></i> High growth<br>
    <br>
    <b>Predictions (2026-2030):</b><br>
    <i style="background: #3498db; width: 18px; height: 18px; display: inline-block; margin-right: 5px;"></i> 2026 (Blue)<br>
    <i style="background: #9b59b6; width: 18px; height: 18px; display: inline-block; margin-right: 5px;"></i> 2027 (Purple)<br>
    <i style="background: #1abc9c; width: 18px; height: 18px; display: inline-block; margin-right: 5px;"></i> 2028 (Teal)<br>
    <i style="background: #e74c3c; width: 18px; height: 18px; display: inline-block; margin-right: 5px;"></i> 2029 (Red)<br>
    <i style="background: #f39c12; width: 18px; height: 18px; display: inline-block; margin-right: 5px;"></i> 2030 (Orange)<br>
</div>
'''
m.get_root().html.add_child(folium.Element(legend_html))

# Save
output_file = output_dir / "time_slider_map.html"
m.save(output_file)
print(f"\nSaved: {output_file}")

print("\n" + "=" * 60)
print("DONE! Open the map in a browser to see the timeline.")
print("Use the time slider at the bottom to navigate from 2015 to 2030.")
print("=" * 60)
