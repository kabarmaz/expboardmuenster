#!/usr/bin/env python3
"""
Animated Spatial Grid Map: 2015-2025 + Predictions
- Cumulative growth shown as layers (like original)
- Prediction overlay after 2025
- Direction arrows rotated 90 degrees counterclockwise
"""

import geopandas as gpd
import pandas as pd
import numpy as np
import folium
from folium import plugins
from pathlib import Path
import json
from shapely import affinity
import warnings
warnings.filterwarnings('ignore')

output_dir = Path("output/interactive")
output_dir.mkdir(parents=True, exist_ok=True)

print("Loading and processing data...")

# Load building growth summary for the timeline
summary_df = pd.read_csv("output/building_growth_summary.csv")
summary_df['period_end'] = pd.to_datetime(summary_df['period_end'])

# Load grid with direction info
grid = gpd.read_file("output/spatial_stats/grid_with_direction.geojson")
grid = grid.to_crs(epsg=4326)

# Load prediction data
predictions = gpd.read_file("output/growth_prediction/predicted_growth_areas.geojson")
predictions = predictions.to_crs(epsg=4326)

# Load forecast data
forecast_df = pd.read_csv("output/forecasting/forecasts.csv")
forecast_df['date'] = pd.to_datetime(forecast_df['date'])

print(f"Grid cells: {len(grid)}")
print(f"Periods in summary: {len(summary_df)}")

# Get period columns and calculate totals
period_cols = [c for c in grid.columns if c.startswith('new_')]
grid['total_new'] = grid[period_cols].sum(axis=1)

# City center
CITY_CENTER = [51.9625, 7.6261]

# ============================================================
# Build timeline data
# ============================================================
print("\nPreparing timeline data...")

timeline_periods = []
cumulative = 0
base_buildings = 105422
total_growth = 0

for idx, row in summary_df.iterrows():
    period_date = row['period_end'].strftime('%Y-%m-%d')
    new_buildings = row['new_buildings'] if row['new_buildings'] < 50000 else 0
    cumulative += new_buildings
    total_growth += new_buildings
    timeline_periods.append({
        'date': period_date,
        'label': row['period_end'].strftime('%Y-%m'),
        'new': new_buildings,
        'cumulative': base_buildings + cumulative,
        'fraction': 0,  # Will calculate after
        'type': 'historical'
    })

# Calculate fractions
for p in timeline_periods:
    p['fraction'] = sum([t['new'] for t in timeline_periods if t['date'] <= p['date']]) / total_growth if total_growth > 0 else 0

# Add forecast periods
for idx, row in forecast_df.iterrows():
    period_date = row['date'].strftime('%Y-%m-%d')
    new_buildings = max(row['ensemble'], 0)
    cumulative += new_buildings
    timeline_periods.append({
        'date': period_date,
        'label': row['date'].strftime('%Y-%m'),
        'new': new_buildings,
        'cumulative': base_buildings + cumulative,
        'fraction': 1.0,
        'type': 'forecast'
    })

print(f"Total timeline periods: {len(timeline_periods)}")

# ============================================================
# Create map with FeatureGroups for each period
# ============================================================
print("\nCreating map with cumulative layers...")

m = folium.Map(location=CITY_CENTER, zoom_start=11, tiles='cartodbpositron')

# Color function
def get_color(intensity):
    """Yellow to Red gradient"""
    r = 255
    g = int(255 * (1 - intensity))
    b = int(100 * (1 - intensity))
    return f'#{r:02x}{g:02x}{b:02x}'

max_new = grid['total_new'].quantile(0.95)
active_cells = grid[grid['total_new'] > 0].copy()

# Create feature groups for key time periods
# Select representative periods (every ~2 years for history + forecasts)
key_periods = [
    timeline_periods[0],   # 2015-06
    timeline_periods[4],   # 2017-06
    timeline_periods[8],   # 2019-06
    timeline_periods[12],  # 2021-05
    timeline_periods[16],  # 2023-05
    timeline_periods[20],  # 2025-01
]
# Add forecast periods
key_periods.extend([p for p in timeline_periods if p['type'] == 'forecast'])

print(f"Creating {len(key_periods)} layer groups...")

for period_idx, period in enumerate(key_periods):
    fraction = period['fraction']
    is_forecast = period['type'] == 'forecast'
    
    layer_name = f"{'🔮 ' if is_forecast else '📊 '}{period['label']}"
    fg = folium.FeatureGroup(name=layer_name, show=(period_idx == len(key_periods) - 1))  # Show last by default
    
    for idx, row in active_cells.iterrows():
        buildings_at_time = row['total_new'] * fraction
        
        if buildings_at_time > 0.5:
            intensity = min(buildings_at_time / max_new, 1)
            color = get_color(intensity)
            
            # Scale geometry for visibility
            scaled_geom = affinity.scale(row['geometry'], xfact=1.8, yfact=1.8, origin='centroid')
            
            popup_html = f"""
            <div style="font-family: Arial; width: 180px;">
                <b>📍 Cell {row['cell_id']}</b><br>
                <hr style="margin: 5px 0;">
                <b>Period:</b> {period['label']}<br>
                <b>Buildings:</b> {buildings_at_time:.0f}<br>
                <b>Direction:</b> {row['direction']}<br>
                <b>Distance:</b> {row['distance_km']:.1f} km
            </div>
            """
            
            folium.GeoJson(
                scaled_geom.__geo_interface__,
                style_function=lambda x, c=color: {
                    'fillColor': c,
                    'color': '#333',
                    'weight': 1,
                    'fillOpacity': 0.75
                },
                popup=folium.Popup(popup_html, max_width=200)
            ).add_to(fg)
    
    # Add prediction cells for forecast periods
    if is_forecast:
        high_pot = predictions[predictions['dev_potential'] > 0.4]
        for idx, row in high_pot.iterrows():
            scaled_geom = affinity.scale(row['geometry'], xfact=1.8, yfact=1.8, origin='centroid')
            
            popup_html = f"""
            <div style="font-family: Arial;">
                <b style="color: #9b59b6;">🔮 Predicted Zone</b><br>
                <b>Potential:</b> {row['dev_potential']:.2f}<br>
                <b>Direction:</b> {row['direction']}
            </div>
            """
            
            folium.GeoJson(
                scaled_geom.__geo_interface__,
                style_function=lambda x: {
                    'fillColor': '#9b59b6',
                    'color': '#6c3483',
                    'weight': 1.5,
                    'fillOpacity': 0.6
                },
                popup=folium.Popup(popup_html, max_width=180)
            ).add_to(fg)
    
    fg.add_to(m)
    print(f"  Added: {layer_name}")

# ============================================================
# Direction Arrows (Rotated 90° counterclockwise)
# ============================================================
print("\nAdding direction arrows...")

direction_layer = folium.FeatureGroup(name='🧭 Expansion Direction', show=True)

high_pot = predictions[predictions['dev_potential'] > 0.4]
dir_weights = high_pot.groupby('direction')['dev_potential'].sum()
dir_weights = dir_weights / dir_weights.max()

# Direction angles - ROTATED 90° COUNTERCLOCKWISE
dir_angles = {
    'E': -90, 'NE': -45, 'N': 0, 'NW': 45,
    'W': 90, 'SW': 135, 'S': 180, 'SE': -135
}

for direction, weight in dir_weights.items():
    if weight > 0.15:
        angle = dir_angles.get(direction, 0)
        arrow_length = 0.025 + 0.045 * weight
        
        rad = np.radians(90 - angle)
        end_lat = CITY_CENTER[0] + arrow_length * np.sin(rad)
        end_lon = CITY_CENTER[1] + arrow_length * np.cos(rad)
        
        opacity = 0.5 + 0.5 * weight
        line_weight = 3 + 6 * weight
        
        folium.PolyLine(
            locations=[[CITY_CENTER[0], CITY_CENTER[1]], [end_lat, end_lon]],
            color='#e74c3c',
            weight=line_weight,
            opacity=opacity,
            popup=f'{direction}: {weight*100:.0f}% growth potential'
        ).add_to(direction_layer)
        
        folium.RegularPolygonMarker(
            location=[end_lat, end_lon],
            number_of_sides=3,
            radius=8 + 5 * weight,
            rotation=angle - 90,
            color='#c0392b',
            fill_color='#e74c3c',
            fill_opacity=opacity
        ).add_to(direction_layer)
        
        label_lat = end_lat + 0.01 * np.sin(rad)
        label_lon = end_lon + 0.01 * np.cos(rad)
        folium.Marker(
            [label_lat, label_lon],
            icon=folium.DivIcon(
                html=f'<div style="font-size: 12px; font-weight: bold; color: #c0392b; text-shadow: 1px 1px 2px white;">{direction}</div>',
                icon_size=(30, 15),
                icon_anchor=(15, 7)
            )
        ).add_to(direction_layer)

direction_layer.add_to(m)

# City center marker
folium.Marker(
    CITY_CENTER,
    popup='<b>Münster City Center</b>',
    icon=folium.Icon(color='blue', icon='star', prefix='fa')
).add_to(m)

# Layer control
folium.LayerControl(collapsed=False).add_to(m)

# ============================================================
# Legend & UI
# ============================================================
legend_html = '''
<div style="
    position: fixed;
    top: 80px;
    right: 20px;
    background: white;
    border-radius: 10px;
    padding: 15px;
    box-shadow: 0 2px 10px rgba(0,0,0,0.2);
    z-index: 1000;
    font-family: Arial, sans-serif;
    font-size: 12px;
    max-width: 200px;
">
    <b style="font-size: 13px;">🗺️ Map Legend</b><br><br>
    
    <b>Growth Intensity</b><br>
    <div style="display: flex; align-items: center; margin: 5px 0;">
        <div style="width: 60px; height: 12px; background: linear-gradient(to right, #ffff64, #ff8064, #ff0064);"></div>
        <span style="margin-left: 5px;">Low → High</span>
    </div>
    
    <b style="margin-top: 10px; display: block;">Predicted (2025+)</b><br>
    <div style="display: flex; align-items: center; margin: 3px 0;">
        <div style="width: 15px; height: 15px; background: #9b59b6; border-radius: 3px;"></div>
        <span style="margin-left: 8px;">Development Zone</span>
    </div>
    
    <b style="margin-top: 10px; display: block;">Direction</b><br>
    <div style="display: flex; align-items: center; margin: 3px 0;">
        <div style="color: #e74c3c; font-size: 16px;">→</div>
        <span style="margin-left: 8px;">Growth Vector</span>
    </div>
    
    <hr style="margin: 10px 0;">
    <small>Toggle periods using<br>layer control on left</small>
</div>
'''
m.get_root().html.add_child(folium.Element(legend_html))

title_html = '''
<div style="
    position: fixed;
    top: 10px;
    left: 50%;
    transform: translateX(-50%);
    background: white;
    padding: 12px 25px;
    border-radius: 25px;
    box-shadow: 0 2px 10px rgba(0,0,0,0.2);
    z-index: 1000;
    font-family: Arial, sans-serif;
">
    <b style="font-size: 16px;">🏙️ Münster Urban Expansion</b>
    <span style="color: #666; margin-left: 10px;">2015 → 2027</span>
</div>
'''
m.get_root().html.add_child(folium.Element(title_html))

stats_html = '''
<div style="
    position: fixed;
    bottom: 30px;
    left: 20px;
    background: white;
    border-radius: 10px;
    padding: 12px;
    box-shadow: 0 2px 10px rgba(0,0,0,0.2);
    z-index: 1000;
    font-family: Arial, sans-serif;
    font-size: 11px;
">
    <b>📊 Summary</b><br>
    <table style="margin-top: 5px;">
        <tr><td>2015:</td><td style="padding-left: 8px;"><b>105,422</b></td></tr>
        <tr><td>2025:</td><td style="padding-left: 8px;"><b>135,576</b></td></tr>
        <tr><td style="color: #9b59b6;">2027:</td><td style="padding-left: 8px; color: #9b59b6;"><b>~137,400</b></td></tr>
    </table>
    <div style="margin-top: 8px; color: #e74c3c;">
        <b>↓ Primary: South</b>
    </div>
</div>
'''
m.get_root().html.add_child(folium.Element(stats_html))

# Save
m.save(output_dir / "animated_grid_map.html")
print(f"\nSaved: {output_dir / 'animated_grid_map.html'}")

print("\nFeatures:")
print("  ✓ Cumulative growth layers (2015 → 2025)")
print("  ✓ Toggle periods via layer control")
print("  ✓ Prediction zones in forecast layers")
print("  ✓ Direction arrows (rotated 90° left)")
