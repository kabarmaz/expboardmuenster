#!/usr/bin/env python3
"""
Interactive Time-Slider Map for Urban Expansion
Uses Folium to create an HTML map with temporal visualization
"""

import geopandas as gpd
import pandas as pd
import numpy as np
import folium
from folium import plugins
from pathlib import Path
import json

# Setup
output_dir = Path("output/interactive")
output_dir.mkdir(parents=True, exist_ok=True)

print("Loading data...")
grid = gpd.read_file("output/spatial_stats/grid_with_direction.geojson")

# Get period columns
period_cols = [c for c in grid.columns if c.startswith('new_')]
period_cols = sorted(period_cols)

print(f"Found {len(period_cols)} time periods")
print("Periods:", [c.replace('new_', '') for c in period_cols])

# Make sure geometry is in WGS84 for Folium
grid = grid.to_crs(epsg=4326)

# Calculate total for coloring
grid['total_new'] = grid[period_cols].sum(axis=1)

# Get center coordinates
center_lat = grid.geometry.centroid.y.mean()
center_lon = grid.geometry.centroid.x.mean()

print(f"Map center: {center_lat:.4f}, {center_lon:.4f}")

# ============================================================
print("\n" + "=" * 60)
print("1. CREATING STATIC OVERVIEW MAP")
print("=" * 60)

# Create base map
m = folium.Map(location=[center_lat, center_lon], zoom_start=11, tiles='cartodbpositron')

# Add choropleth for total new buildings
def get_color(value, max_val):
    if value == 0:
        return '#f0f0f0'
    ratio = min(value / max_val, 1)
    # Yellow to Red gradient
    r = 255
    g = int(255 * (1 - ratio))
    b = 0
    return f'#{r:02x}{g:02x}{b:02x}'

max_new = grid['total_new'].quantile(0.95)  # Use 95th percentile for coloring

# Add grid cells
for idx, row in grid[grid['total_new'] > 0].iterrows():
    color = get_color(row['total_new'], max_new)
    popup_text = f"""
    <b>Cell {row['cell_id']}</b><br>
    Direction: {row['direction']}<br>
    Distance: {row['distance_km']:.1f} km<br>
    Total New: {row['total_new']:.0f}<br>
    """
    
    folium.GeoJson(
        row['geometry'].__geo_interface__,
        style_function=lambda x, c=color: {
            'fillColor': c,
            'color': 'gray',
            'weight': 0.5,
            'fillOpacity': 0.7
        },
        popup=folium.Popup(popup_text, max_width=200)
    ).add_to(m)

# Add city center marker
folium.Marker(
    [51.9625, 7.6261],
    popup='Münster City Center',
    icon=folium.Icon(color='blue', icon='star')
).add_to(m)

# Add legend
legend_html = '''
<div style="position: fixed; bottom: 50px; left: 50px; z-index: 1000; 
            background-color: white; padding: 10px; border: 2px solid gray;
            border-radius: 5px; font-size: 12px;">
    <b>New Buildings</b><br>
    <i style="background: #ffff00; width: 18px; height: 18px; display: inline-block; margin-right: 5px;"></i> Low<br>
    <i style="background: #ff8000; width: 18px; height: 18px; display: inline-block; margin-right: 5px;"></i> Medium<br>
    <i style="background: #ff0000; width: 18px; height: 18px; display: inline-block; margin-right: 5px;"></i> High
</div>
'''
m.get_root().html.add_child(folium.Element(legend_html))

m.save(output_dir / "overview_map.html")
print(f"Saved: {output_dir / 'overview_map.html'}")

# ============================================================
print("\n" + "=" * 60)
print("2. CREATING TIME-SLIDER MAP")
print("=" * 60)

# Create a map with time slider using folium plugins
m2 = folium.Map(location=[center_lat, center_lon], zoom_start=11, tiles='cartodbpositron')

# Prepare features for each time period
features_by_time = {}

for period in period_cols:
    period_date = period.replace('new_', '')
    features = []
    
    for idx, row in grid.iterrows():
        value = row[period]
        if value > 0:
            # Create feature
            feat = {
                'type': 'Feature',
                'geometry': row['geometry'].__geo_interface__,
                'properties': {
                    'time': period_date,
                    'new_buildings': int(value),
                    'direction': row['direction'],
                    'style': {
                        'fillColor': get_color(value, max_new / len(period_cols)),
                        'color': 'gray',
                        'weight': 0.5,
                        'fillOpacity': 0.7
                    }
                }
            }
            features.append(feat)
    
    features_by_time[period_date] = features
    print(f"  {period_date}: {len(features)} active cells")

# Create GeoJSON with all timestamped features
all_features = []
for period_date, feats in features_by_time.items():
    for f in feats:
        # Add time as ISO format for TimestampedGeoJson
        f['properties']['time'] = period_date + 'T00:00:00'
        all_features.append(f)

geojson_data = {
    'type': 'FeatureCollection',
    'features': all_features
}

# Add TimestampedGeoJson
plugins.TimestampedGeoJson(
    geojson_data,
    period='P6M',  # 6 months
    add_last_point=True,
    auto_play=False,
    loop=False,
    max_speed=1,
    loop_button=True,
    date_options='YYYY-MM-DD',
    time_slider_drag_update=True
).add_to(m2)

# Add city center marker
folium.Marker(
    [51.9625, 7.6261],
    popup='Münster City Center',
    icon=folium.Icon(color='blue', icon='star')
).add_to(m2)

m2.save(output_dir / "time_slider_map.html")
print(f"\nSaved: {output_dir / 'time_slider_map.html'}")

# ============================================================
print("\n" + "=" * 60)
print("3. CREATING DIRECTION LAYER MAP")
print("=" * 60)

m3 = folium.Map(location=[center_lat, center_lon], zoom_start=11, tiles='cartodbpositron')

# Color by direction
dir_colors = {
    'N': '#1f77b4', 'NE': '#ff7f0e', 'E': '#2ca02c', 'SE': '#d62728',
    'S': '#9467bd', 'SW': '#8c564b', 'W': '#e377c2', 'NW': '#7f7f7f'
}

# Create feature groups for each direction
direction_groups = {d: folium.FeatureGroup(name=f'{d} Direction') for d in dir_colors.keys()}

for idx, row in grid[grid['total_new'] > 0].iterrows():
    direction = row['direction']
    color = dir_colors.get(direction, 'gray')
    
    popup_text = f"""
    <b>Cell {row['cell_id']}</b><br>
    Direction: {direction}<br>
    Distance: {row['distance_km']:.1f} km<br>
    New buildings: {row['total_new']:.0f}
    """
    
    folium.GeoJson(
        row['geometry'].__geo_interface__,
        style_function=lambda x, c=color: {
            'fillColor': c,
            'color': 'white',
            'weight': 0.5,
            'fillOpacity': 0.6
        },
        popup=folium.Popup(popup_text, max_width=200)
    ).add_to(direction_groups[direction])

# Add all direction groups to map
for direction, group in direction_groups.items():
    group.add_to(m3)

# Add layer control
folium.LayerControl(collapsed=False).add_to(m3)

# Add city center marker
folium.Marker(
    [51.9625, 7.6261],
    popup='Münster City Center',
    icon=folium.Icon(color='blue', icon='star')
).add_to(m3)

# Add legend
legend_html_dir = '''
<div style="position: fixed; bottom: 50px; left: 50px; z-index: 1000; 
            background-color: white; padding: 10px; border: 2px solid gray;
            border-radius: 5px; font-size: 12px;">
    <b>Growth Direction</b><br>
'''
for d, c in dir_colors.items():
    legend_html_dir += f'<i style="background: {c}; width: 18px; height: 18px; display: inline-block; margin-right: 5px;"></i> {d}<br>'
legend_html_dir += '</div>'
m3.get_root().html.add_child(folium.Element(legend_html_dir))

m3.save(output_dir / "direction_map.html")
print(f"Saved: {output_dir / 'direction_map.html'}")

# ============================================================
print("\n" + "=" * 60)
print("4. SUMMARY STATISTICS")
print("=" * 60)

# Create summary JSON for potential dashboard
summary = {
    'periods': len(period_cols),
    'total_cells': len(grid),
    'cells_with_growth': len(grid[grid['total_new'] > 0]),
    'total_new_buildings': int(grid['total_new'].sum()),
    'growth_by_direction': grid.groupby('direction')['total_new'].sum().to_dict(),
    'period_dates': [c.replace('new_', '') for c in period_cols]
}

with open(output_dir / 'map_summary.json', 'w') as f:
    json.dump(summary, f, indent=2)
print(f"Saved: {output_dir / 'map_summary.json'}")

print("\n" + "=" * 60)
print("INTERACTIVE MAPS COMPLETE")
print("=" * 60)
print(f"\nOpen these files in a browser:")
print(f"  1. {output_dir / 'overview_map.html'} - Total growth overview")
print(f"  2. {output_dir / 'time_slider_map.html'} - Animated time slider")
print(f"  3. {output_dir / 'direction_map.html'} - Growth by direction")
