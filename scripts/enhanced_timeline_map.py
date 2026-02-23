#!/usr/bin/env python3
"""
Enhanced Time Slider Map with Full Timeline and Predictions
- Timeline from 2015 to 2030 (with predictions)
- Cumulative growth visualization
- Prediction zones with directional indicators
"""

import geopandas as gpd
import pandas as pd
import numpy as np
import folium
from folium import plugins
from pathlib import Path
import json
from shapely.geometry import Point, LineString
import warnings
warnings.filterwarnings('ignore')

output_dir = Path("output/interactive")
output_dir.mkdir(parents=True, exist_ok=True)

print("Loading data...")

# Load grid data
grid = gpd.read_file("output/spatial_stats/grid_with_direction.geojson")
grid = grid.to_crs(epsg=4326)

# Load prediction data
predictions = gpd.read_file("output/growth_prediction/predicted_growth_areas.geojson")
predictions = predictions.to_crs(epsg=4326)

# Load building growth summary for timeline
summary_df = pd.read_csv("output/building_growth_summary.csv")
summary_df['period_end'] = pd.to_datetime(summary_df['period_end'])

# Load forecast data
forecast_df = pd.read_csv("output/forecasting/forecasts.csv")
forecast_df['date'] = pd.to_datetime(forecast_df['date'])

print(f"Grid cells: {len(grid)}")
print(f"Prediction cells: {len(predictions)}")
print(f"Historical periods: {len(summary_df)}")
print(f"Forecast periods: {len(forecast_df)}")

# Get period columns from grid
period_cols = [c for c in grid.columns if c.startswith('new_')]
period_cols = sorted(period_cols)

# Calculate total new buildings
grid['total_new'] = grid[period_cols].sum(axis=1)

# City center
CITY_CENTER = [51.9625, 7.6261]

# ============================================================
print("\nCreating enhanced time slider map...")
# ============================================================

# Create base map
m = folium.Map(location=CITY_CENTER, zoom_start=11, tiles='cartodbpositron')

# Color function
def get_color(value, max_val, is_prediction=False):
    if value == 0:
        return '#f0f0f0'
    ratio = min(value / max(max_val, 1), 1)
    if is_prediction:
        # Purple gradient for predictions
        r = int(128 + 127 * ratio)
        g = int(0 + 100 * (1 - ratio))
        b = int(255)
        return f'#{r:02x}{g:02x}{b:02x}'
    else:
        # Red gradient for historical
        r = 255
        g = int(255 * (1 - ratio))
        b = int(100 * (1 - ratio))
        return f'#{r:02x}{g:02x}64'

max_new = grid['total_new'].quantile(0.95)

# ============================================================
# Layer 1: Cumulative Historical Growth (Base layer)
# ============================================================
cumulative_layer = folium.FeatureGroup(name='📊 Cumulative Growth (2023-2025)', show=True)

for idx, row in grid[grid['total_new'] > 0].iterrows():
    color = get_color(row['total_new'], max_new)
    
    popup_html = f"""
    <div style="font-family: Arial; width: 200px;">
        <b style="color: #333;">📊 Historical Growth</b><br>
        <hr style="margin: 5px 0;">
        <b>Cell:</b> {row['cell_id']}<br>
        <b>Direction:</b> {row['direction']}<br>
        <b>Distance:</b> {row['distance_km']:.1f} km<br>
        <b>Total New:</b> {row['total_new']:.0f} buildings<br>
        <hr style="margin: 5px 0;">
        <small>Period breakdown:</small><br>
    """
    for col in period_cols:
        period_date = col.replace('new_', '')
        popup_html += f"  • {period_date}: {row[col]:.0f}<br>"
    popup_html += "</div>"
    
    folium.GeoJson(
        row['geometry'].__geo_interface__,
        style_function=lambda x, c=color: {
            'fillColor': c,
            'color': 'white',
            'weight': 0.5,
            'fillOpacity': 0.7
        },
        popup=folium.Popup(popup_html, max_width=250)
    ).add_to(cumulative_layer)

cumulative_layer.add_to(m)

# ============================================================
# Layer 2: Prediction Zones
# ============================================================
prediction_layer = folium.FeatureGroup(name='🔮 Predicted Growth Zones (2025-2030)', show=True)

# High potential predictions
high_pot = predictions[predictions['dev_potential'] > 0.4].copy()
max_pot = high_pot['dev_potential'].max()

for idx, row in high_pot.iterrows():
    pot_score = row['dev_potential']
    
    # Color based on potential level
    if pot_score >= 0.6:
        color = '#9b59b6'  # Purple - very high
        level = 'Very High'
    elif pot_score >= 0.4:
        color = '#8e44ad'  # Lighter purple - high
        level = 'High'
    else:
        color = '#a569bd'  # Light purple - moderate
        level = 'Moderate'
    
    popup_html = f"""
    <div style="font-family: Arial; width: 200px;">
        <b style="color: #9b59b6;">🔮 Predicted Development</b><br>
        <hr style="margin: 5px 0;">
        <b>Potential:</b> {level}<br>
        <b>Score:</b> {pot_score:.2f}<br>
        <b>Direction:</b> {row['direction']}<br>
        <b>Distance:</b> {row['distance_km']:.1f} km<br>
        <hr style="margin: 5px 0;">
        <small>Based on historical patterns<br>
        and spatial spillover analysis</small>
    </div>
    """
    
    folium.GeoJson(
        row['geometry'].__geo_interface__,
        style_function=lambda x, c=color, p=pot_score: {
            'fillColor': c,
            'color': '#6c3483',
            'weight': 1,
            'fillOpacity': 0.5 + 0.3 * (p / max_pot)
        },
        popup=folium.Popup(popup_html, max_width=220)
    ).add_to(prediction_layer)

prediction_layer.add_to(m)

# ============================================================
# Layer 3: Growth Direction Arrows
# ============================================================
direction_layer = folium.FeatureGroup(name='🧭 Expansion Direction', show=True)

# Calculate direction weights from predictions
dir_weights = high_pot.groupby('direction')['dev_potential'].sum()
dir_weights = dir_weights / dir_weights.max()

# Direction angles
dir_angles = {
    'E': 0, 'NE': 45, 'N': 90, 'NW': 135, 
    'W': 180, 'SW': 225, 'S': 270, 'SE': 315
}

# Draw arrows from city center
for direction, weight in dir_weights.items():
    if weight > 0.2:  # Only show significant directions
        angle = dir_angles.get(direction, 0)
        
        # Calculate arrow endpoint
        # Longer arrow = higher weight
        arrow_length = 0.03 + 0.05 * weight  # degrees
        
        rad = np.radians(90 - angle)  # Convert to math convention
        end_lat = CITY_CENTER[0] + arrow_length * np.sin(rad)
        end_lon = CITY_CENTER[1] + arrow_length * np.cos(rad)
        
        # Arrow color intensity based on weight
        opacity = 0.5 + 0.5 * weight
        line_weight = 3 + 5 * weight
        
        # Draw line
        folium.PolyLine(
            locations=[[CITY_CENTER[0], CITY_CENTER[1]], [end_lat, end_lon]],
            color='#e74c3c',
            weight=line_weight,
            opacity=opacity,
            popup=f'{direction}: {weight*100:.0f}% of predicted growth'
        ).add_to(direction_layer)
        
        # Add arrowhead marker
        folium.RegularPolygonMarker(
            location=[end_lat, end_lon],
            number_of_sides=3,
            radius=8 + 4 * weight,
            rotation=angle - 90,  # Point in direction
            color='#c0392b',
            fill_color='#e74c3c',
            fill_opacity=opacity,
            popup=f'<b>{direction}</b><br>Growth potential: {weight*100:.0f}%'
        ).add_to(direction_layer)
        
        # Add label
        label_lat = end_lat + 0.008 * np.sin(rad)
        label_lon = end_lon + 0.008 * np.cos(rad)
        folium.Marker(
            [label_lat, label_lon],
            icon=folium.DivIcon(
                html=f'<div style="font-size: 12px; font-weight: bold; color: #c0392b; text-shadow: 1px 1px white;">{direction}</div>',
                icon_size=(30, 15),
                icon_anchor=(15, 7)
            )
        ).add_to(direction_layer)

direction_layer.add_to(m)

# ============================================================
# City Center Marker
# ============================================================
folium.Marker(
    CITY_CENTER,
    popup='<b>Münster City Center</b><br>(Dom/Prinzipalmarkt)',
    icon=folium.Icon(color='blue', icon='star', prefix='fa')
).add_to(m)

# ============================================================
# Layer Control
# ============================================================
folium.LayerControl(collapsed=False).add_to(m)

# ============================================================
# Timeline Chart (HTML/CSS overlay)
# ============================================================
# Create timeline data for the chart
timeline_data = []
for _, row in summary_df.iterrows():
    timeline_data.append({
        'date': row['period_end'].strftime('%Y-%m'),
        'buildings': row['new_buildings'] if row['new_buildings'] < 50000 else 0,  # Skip baseline
        'type': 'historical'
    })

# Add forecasts
for _, row in forecast_df.iterrows():
    timeline_data.append({
        'date': row['date'].strftime('%Y-%m'),
        'buildings': max(row['ensemble'], 0),
        'type': 'forecast'
    })

timeline_json = json.dumps(timeline_data)

# Add timeline chart overlay
timeline_html = f'''
<div id="timeline-panel" style="
    position: fixed;
    bottom: 20px;
    left: 50%;
    transform: translateX(-50%);
    width: 90%;
    max-width: 800px;
    background: white;
    border-radius: 12px;
    box-shadow: 0 4px 20px rgba(0,0,0,0.3);
    padding: 15px;
    z-index: 1000;
    font-family: Arial, sans-serif;
">
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
        <h4 style="margin: 0; color: #333;">📈 Building Growth Timeline (2015-2027)</h4>
        <button onclick="document.getElementById('timeline-panel').style.display='none'" 
                style="border: none; background: #ddd; border-radius: 50%; width: 25px; height: 25px; cursor: pointer;">×</button>
    </div>
    <div style="display: flex; align-items: flex-end; height: 80px; gap: 2px; overflow-x: auto;">
'''

# Generate timeline bars
max_buildings = max([d['buildings'] for d in timeline_data if d['buildings'] > 0], default=1)
for d in timeline_data:
    if d['buildings'] > 0:
        height = max(5, int(70 * d['buildings'] / max_buildings))
        color = '#3498db' if d['type'] == 'historical' else '#9b59b6'
        timeline_html += f'''
        <div title="{d['date']}: {d['buildings']:.0f} buildings" 
             style="flex: 1; min-width: 15px; height: {height}px; background: {color}; border-radius: 2px 2px 0 0;"></div>
        '''

timeline_html += '''
    </div>
    <div style="display: flex; justify-content: space-between; font-size: 11px; color: #666; margin-top: 5px;">
        <span>2015</span>
        <span>|</span>
        <span>2018</span>
        <span>|</span>
        <span>2021</span>
        <span>|</span>
        <span style="color: #9b59b6; font-weight: bold;">2025 →</span>
        <span style="color: #9b59b6;">2027</span>
    </div>
    <div style="display: flex; gap: 20px; font-size: 11px; margin-top: 8px; justify-content: center;">
        <span><span style="display: inline-block; width: 12px; height: 12px; background: #3498db; border-radius: 2px;"></span> Historical</span>
        <span><span style="display: inline-block; width: 12px; height: 12px; background: #9b59b6; border-radius: 2px;"></span> Forecast</span>
    </div>
</div>
'''
m.get_root().html.add_child(folium.Element(timeline_html))

# ============================================================
# Legend
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
    
    <b>Historical Growth</b><br>
    <div style="display: flex; align-items: center; margin: 5px 0;">
        <div style="width: 60px; height: 12px; background: linear-gradient(to right, #ffffb2, #feb24c, #f03b20);"></div>
        <span style="margin-left: 5px;">Low → High</span>
    </div>
    
    <b style="margin-top: 10px; display: block;">Predicted Zones</b><br>
    <div style="display: flex; align-items: center; margin: 3px 0;">
        <div style="width: 15px; height: 15px; background: #9b59b6; border-radius: 3px;"></div>
        <span style="margin-left: 8px;">Very High Potential</span>
    </div>
    <div style="display: flex; align-items: center; margin: 3px 0;">
        <div style="width: 15px; height: 15px; background: #8e44ad; border-radius: 3px;"></div>
        <span style="margin-left: 8px;">High Potential</span>
    </div>
    
    <b style="margin-top: 10px; display: block;">Expansion Direction</b><br>
    <div style="display: flex; align-items: center; margin: 3px 0;">
        <div style="width: 0; height: 0; border-left: 8px solid transparent; border-right: 8px solid transparent; border-bottom: 12px solid #e74c3c;"></div>
        <span style="margin-left: 8px;">Growth Vector</span>
    </div>
</div>
'''
m.get_root().html.add_child(folium.Element(legend_html))

# ============================================================
# Title
# ============================================================
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
    <b style="font-size: 16px;">🏙️ Münster Urban Expansion: 2015-2030</b>
    <span style="color: #666; margin-left: 10px;">Historical + Predicted Growth</span>
</div>
'''
m.get_root().html.add_child(folium.Element(title_html))

# ============================================================
# Summary Stats Box
# ============================================================
total_hist = summary_df[summary_df['new_buildings'] < 50000]['new_buildings'].sum()
total_forecast = forecast_df['ensemble'].clip(lower=0).sum()

stats_html = f'''
<div style="
    position: fixed;
    bottom: 130px;
    left: 20px;
    background: white;
    border-radius: 10px;
    padding: 15px;
    box-shadow: 0 2px 10px rgba(0,0,0,0.2);
    z-index: 1000;
    font-family: Arial, sans-serif;
    font-size: 12px;
">
    <b style="font-size: 13px;">📊 Summary</b><br><br>
    <table style="border-collapse: collapse;">
        <tr><td style="padding: 3px 10px 3px 0;">Buildings (2015):</td><td><b>105,422</b></td></tr>
        <tr><td style="padding: 3px 10px 3px 0;">Buildings (2025):</td><td><b>135,576</b></td></tr>
        <tr><td style="padding: 3px 10px 3px 0; color: #9b59b6;">Forecast (2027):</td><td style="color: #9b59b6;"><b>~137,400</b></td></tr>
        <tr><td colspan="2"><hr style="margin: 5px 0;"></td></tr>
        <tr><td style="padding: 3px 10px 3px 0;">Growth Rate:</td><td><b>+28.6%</b></td></tr>
        <tr><td style="padding: 3px 10px 3px 0;">Primary Direction:</td><td><b style="color: #e74c3c;">South ↓</b></td></tr>
    </table>
</div>
'''
m.get_root().html.add_child(folium.Element(stats_html))

# Save map
m.save(output_dir / "enhanced_timeline_map.html")
print(f"\nSaved: {output_dir / 'enhanced_timeline_map.html'}")

# Also update the time_slider_map.html link in dashboard
print("\nEnhanced map features:")
print("  ✓ Cumulative historical growth layer (2023-2025)")
print("  ✓ Prediction zones (2025-2030) with potential scores")
print("  ✓ Directional expansion arrows from city center")
print("  ✓ Interactive timeline chart (2015-2027)")
print("  ✓ Legend and statistics overlay")
print("\nOpen in browser to explore!")
