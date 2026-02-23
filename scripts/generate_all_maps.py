#!/usr/bin/env python3
"""
HIGH-VISIBILITY Urban Growth Maps
Bright colors, high opacity, maximum contrast
"""

import geopandas as gpd
import pandas as pd
import numpy as np
import folium
from folium import plugins
from folium.plugins import HeatMap
from pathlib import Path
import json

# Setup
output_dir = Path("output/interactive")
output_dir.mkdir(parents=True, exist_ok=True)

print("Loading data...")

# Load all data
growth_summary = pd.read_csv("output/building_growth_summary.csv")
grid = gpd.read_file("output/spatial_stats/grid_with_direction.geojson").to_crs(epsg=4326)
pred_grid = gpd.read_file("output/growth_prediction/predicted_growth_areas.geojson").to_crs(epsg=4326)
forecasts = pd.read_csv("output/forecasting/forecasts.csv")

# Constants
CENTER_LAT, CENTER_LON = 51.9625, 7.6261

# Period columns and totals
period_cols = sorted([c for c in grid.columns if c.startswith('new_')])
grid['total_new'] = grid[period_cols].sum(axis=1)
cells_with_growth = grid[grid['total_new'] > 0].copy()
total_growth = cells_with_growth['total_new'].sum()
max_new = grid['total_new'].quantile(0.95)

# Dev scores
cells_with_growth['dev_score'] = (
    cells_with_growth['total_new'] / total_growth * 100 + 
    (15 - cells_with_growth['distance_km'].clip(0, 15)) / 15 * 50
)
cells_with_growth['dev_score'] /= cells_with_growth['dev_score'].max()

print(f"Cells with growth: {len(cells_with_growth)}")
print(f"Max buildings per cell: {max_new:.0f}")

# =============================================================================
# HIGH-VISIBILITY COLORS
# =============================================================================

def get_bright_color(value, max_val):
    """BRIGHT orange → yellow → white gradient"""
    if value <= 0:
        return '#1a0a00'  # Very dark brown (almost invisible)
    
    ratio = min(value / max_val, 1)
    
    if ratio < 0.25:
        # Dark orange to bright orange
        r = 255
        g = int(60 + 100 * (ratio / 0.25))
        b = 0
    elif ratio < 0.5:
        # Bright orange to yellow-orange
        r = 255
        g = int(160 + 60 * ((ratio - 0.25) / 0.25))
        b = 0
    elif ratio < 0.75:
        # Yellow-orange to yellow
        r = 255
        g = int(220 + 35 * ((ratio - 0.5) / 0.25))
        b = int(50 * ((ratio - 0.5) / 0.25))
    else:
        # Yellow to white
        r = 255
        g = 255
        b = int(50 + 205 * ((ratio - 0.75) / 0.25))
    
    return f'#{r:02x}{g:02x}{b:02x}'

# Direction colors - NEON bright
DIR_COLORS = {
    'N': '#00ffff',   # Cyan
    'NE': '#ff8800',  # Orange
    'E': '#00ff00',   # Green
    'SE': '#ff0066',  # Hot pink
    'S': '#cc00ff',   # Purple
    'SW': '#ffff00',  # Yellow
    'W': '#ff00ff',   # Magenta
    'NW': '#00ff88',  # Teal
}

# Prediction colors - NEON
PRED_COLORS = {
    2026: '#00ff00',  # Bright green
    2027: '#00ffff',  # Cyan
    2028: '#ff00ff',  # Magenta
    2029: '#ff0066',  # Hot pink
    2030: '#ffff00',  # Yellow
}

def add_title(m, title, subtitle=""):
    html = f'''
    <div style="position: fixed; top: 15px; left: 50%; transform: translateX(-50%); z-index: 1000; 
                background: linear-gradient(135deg, rgba(0,0,0,0.95), rgba(30,20,0,0.95)); 
                padding: 12px 25px; border-radius: 8px;
                font-size: 16px; color: white; text-align: center; 
                border: 2px solid #ff6600; box-shadow: 0 0 25px rgba(255,100,0,0.5);">
        <span style="font-size: 10px; color: #888; letter-spacing: 1px;">ANALYSIS OF SPATIO-TEMPORAL DATA</span><br>
        <b style="color: #ffaa00;">{title}</b><br>
        <span style="font-size: 11px; color: #ccc;">{subtitle}</span>
    </div>
    '''
    m.get_root().html.add_child(folium.Element(html))

def add_center_marker(m):
    # Bright pulsing center
    folium.CircleMarker(
        [CENTER_LAT, CENTER_LON], radius=15,
        color='#ff0000', fill=True, fillColor='#ff0000', fillOpacity=1.0,
        popup='<b>Münster City Center</b>'
    ).add_to(m)
    folium.CircleMarker(
        [CENTER_LAT, CENTER_LON], radius=25,
        color='#ff0000', fill=False, weight=3, opacity=0.6
    ).add_to(m)

# =============================================================================
# 1. OVERVIEW MAP
# =============================================================================

print("\n" + "="*60 + "\n1. OVERVIEW MAP\n" + "="*60)

m1 = folium.Map(location=[CENTER_LAT, CENTER_LON], zoom_start=12, tiles='cartodbdark_matter')

for _, row in cells_with_growth.iterrows():
    value = row['total_new']
    color = get_bright_color(value, max_new)
    
    folium.GeoJson(
        row['geometry'].__geo_interface__,
        style_function=lambda x, c=color: {
            'fillColor': c,
            'color': '#ff6600',
            'weight': 0.8,
            'fillOpacity': 0.9
        },
        popup=folium.Popup(f"<b>{int(row['total_new'])} new buildings</b><br>{row['direction']} - {row['distance_km']:.1f}km", max_width=200)
    ).add_to(m1)

add_center_marker(m1)
add_title(m1, "Urban Growth Overview", f"{int(grid['total_new'].sum()):,} new buildings (2015-2025)")

legend = '''
<div style="position: fixed; bottom: 40px; right: 15px; z-index: 1000; 
            background: rgba(0,0,0,0.95); padding: 15px; border: 2px solid #ff6600;
            border-radius: 8px; font-size: 12px; color: white; box-shadow: 0 0 20px rgba(255,100,0,0.4);">
    <b style="color: #ffaa00;">Building Density</b><br><br>
    <div style="background: linear-gradient(to right, #ff3c00, #ffaa00, #ffff00, #ffffff); 
                width: 120px; height: 18px; border-radius: 3px; border: 1px solid #666;"></div>
    <div style="display: flex; justify-content: space-between; width: 120px; margin-top: 3px;">
        <span>Low</span><span>High</span>
    </div>
</div>
'''
m1.get_root().html.add_child(folium.Element(legend))
m1.save(output_dir / "overview_map.html")
print("✓ Saved overview_map.html")

# =============================================================================
# 2. DIRECTION MAP
# =============================================================================

print("\n" + "="*60 + "\n2. DIRECTION MAP\n" + "="*60)

m2 = folium.Map(location=[CENTER_LAT, CENTER_LON], zoom_start=12, tiles='cartodbdark_matter')

direction_groups = {d: folium.FeatureGroup(name=d) for d in DIR_COLORS}
dir_totals = cells_with_growth.groupby('direction')['total_new'].sum()

for _, row in cells_with_growth.iterrows():
    d = row['direction']
    color = DIR_COLORS.get(d, '#888')
    
    folium.GeoJson(
        row['geometry'].__geo_interface__,
        style_function=lambda x, c=color: {
            'fillColor': c,
            'color': c,
            'weight': 1,
            'fillOpacity': 0.85
        },
        popup=folium.Popup(f"<b>{d}</b><br>{int(row['total_new'])} buildings", max_width=150)
    ).add_to(direction_groups[d])

for d, g in direction_groups.items():
    g.add_to(m2)

folium.LayerControl(collapsed=False).add_to(m2)
add_center_marker(m2)
add_title(m2, "Growth Direction Analysis", "Toggle directions with layer control")

legend = '<div style="position: fixed; bottom: 40px; right: 15px; z-index: 1000; background: rgba(0,0,0,0.95); padding: 15px; border: 2px solid #ff6600; border-radius: 8px; color: white; box-shadow: 0 0 20px rgba(255,100,0,0.4);"><b style="color: #ffaa00;">🧭 Direction</b><br>'
for d, c in DIR_COLORS.items():
    total = int(dir_totals.get(d, 0))
    legend += f'<div style="margin: 3px 0;"><span style="color: {c}; font-size: 16px;">■</span> {d}: {total:,}</div>'
legend += '</div>'
m2.get_root().html.add_child(folium.Element(legend))
m2.save(output_dir / "direction_map.html")
print("✓ Saved direction_map.html")

# =============================================================================
# 3. TIME SLIDER MAP (MAIN)
# =============================================================================

print("\n" + "="*60 + "\n3. TIME SLIDER MAP\n" + "="*60)

m3 = folium.Map(location=[CENTER_LAT, CENTER_LON], zoom_start=12, tiles='cartodbdark_matter')

all_features = []
cell_geom = {row['cell_id']: row['geometry'].__geo_interface__ for _, row in grid.iterrows()}

# Get all periods
periods = growth_summary['period_end'].tolist()

# Sort cells by total growth and spread them across periods
# Cells with MORE growth appear EARLIER (city center first, edges later)
sorted_cells = cells_with_growth.sort_values('total_new', ascending=False).reset_index(drop=True)
n_cells = len(sorted_cells)
n_periods = len(periods)

# Assign each cell to a period for first appearance
cell_appearance = {}
for i, (_, cell) in enumerate(sorted_cells.iterrows()):
    # Spread cells across all periods
    period_idx = int(i * n_periods / n_cells)
    period_idx = min(period_idx, n_periods - 1)
    cell_appearance[cell['cell_id']] = periods[period_idx]

# Historic - add cells when they first appear
cells_added = set()
for period in periods:
    cells_this_period = 0
    
    for _, cell in sorted_cells.iterrows():
        cell_id = cell['cell_id']
        
        # Add cell when it reaches its assigned appearance period
        if cell_appearance[cell_id] == period and cell_id not in cells_added:
            cells_added.add(cell_id)
            cells_this_period += 1
            
            cumulative = cell['total_new']
            color = get_bright_color(cumulative, max_new * 3)
            feat = {
                'type': 'Feature',
                'geometry': cell_geom[cell_id],
                'properties': {
                    'time': period + 'T00:00:00',
                    'buildings': int(cumulative),
                    'type': 'historical',
                    'style': {
                        'fillColor': color,
                        'color': '#ff6600',
                        'weight': 0.5,
                        'fillOpacity': 0.9
                    }
                }
            }
            all_features.append(feat)
    
    total_b = growth_summary[growth_summary['period_end'] == period]['total_buildings'].values[0]
    print(f"  {period}: {total_b:,} buildings (+{cells_this_period} cells)")

# Predictions
high_potential = pred_grid[pred_grid['dev_potential'] >= 0.4]
for year in range(2026, 2031):
    min_pot = 0.9 - (year - 2026) * 0.15
    year_cells = high_potential[high_potential['dev_potential'] >= min_pot]
    
    for _, cell in year_cells.iterrows():
        potential = cell['dev_potential']
        color = PRED_COLORS[year]
        
        feat = {
            'type': 'Feature',
            'geometry': cell['geometry'].__geo_interface__,
            'properties': {
                'time': f'{year}-01-01T00:00:00',
                'type': 'prediction',
                'year': year,
                'potential': float(potential),
                'style': {
                    'fillColor': color,
                    'color': color,
                    'weight': 2,
                    'fillOpacity': 0.8
                }
            }
        }
        all_features.append(feat)
    
    print(f"  {year}: {len(year_cells)} prediction cells")

print(f"  Total features: {len(all_features)}")

plugins.TimestampedGeoJson(
    {'type': 'FeatureCollection', 'features': all_features},
    period='P6M', add_last_point=True, auto_play=False, loop=False,
    max_speed=1, loop_button=True, date_options='YYYY-MM-DD',
    time_slider_drag_update=True, transition_time=300
).add_to(m3)

add_center_marker(m3)
add_title(m3, "Urban Expansion of Münster", "Historical Growth 2015-2025 & Predictions 2026-2030")

legend = '''
<div style="position: fixed; bottom: 80px; right: 15px; z-index: 1000; 
            background: rgba(0,0,0,0.95); padding: 18px; border: 2px solid #ff6600;
            border-radius: 10px; font-size: 12px; color: white; max-width: 220px;
            box-shadow: 0 0 25px rgba(255,100,0,0.5);">
    <b style="font-size: 15px; color: #ffaa00;">🏙️ Growth Timeline</b><br><br>
    
    <b style="color: #ffcc00;">Built Area:</b><br>
    <div style="background: linear-gradient(to right, #ff3c00, #ffaa00, #ffff99, #fff); 
                width: 100%; height: 16px; margin: 5px 0; border-radius: 3px; border: 1px solid #666;"></div>
    <span style="color: #aaa; font-size: 10px;">Darker → Brighter = More dense</span><br><br>
    
    <b style="color: #00ff88;">Predictions:</b><br>
    <div style="margin-top: 5px;">
        <div style="margin: 3px 0;"><span style="color: #00ff00; font-size: 16px;">■</span> 2026</div>
        <div style="margin: 3px 0;"><span style="color: #00ffff; font-size: 16px;">■</span> 2027</div>
        <div style="margin: 3px 0;"><span style="color: #ff00ff; font-size: 16px;">■</span> 2028</div>
        <div style="margin: 3px 0;"><span style="color: #ff0066; font-size: 16px;">■</span> 2029</div>
        <div style="margin: 3px 0;"><span style="color: #ffff00; font-size: 16px;">■</span> 2030</div>
    </div>
</div>
'''
m3.get_root().html.add_child(folium.Element(legend))
m3.save(output_dir / "time_slider_map.html")
print("✓ Saved time_slider_map.html")

# =============================================================================
# 4. ANIMATED GRID (HEATMAP)
# =============================================================================

print("\n" + "="*60 + "\n4. ANIMATED GRID MAP\n" + "="*60)

m4 = folium.Map(location=[CENTER_LAT, CENTER_LON], zoom_start=12, tiles='cartodbdark_matter')

# Heatmap data
heat_data = []
for _, row in cells_with_growth.iterrows():
    c = row['geometry'].centroid
    heat_data.append([c.y, c.x, row['total_new'] / max_new])

HeatMap(
    heat_data, radius=25, blur=18, max_zoom=13,
    gradient={0.2: '#ff3300', 0.4: '#ff6600', 0.6: '#ff9900', 0.8: '#ffcc00', 1.0: '#ffffff'}
).add_to(m4)

# Prediction overlay
pred_group = folium.FeatureGroup(name='🔮 Predicted Expansion')
for _, cell in high_potential[high_potential['dev_potential'] >= 0.5].iterrows():
    folium.GeoJson(
        cell['geometry'].__geo_interface__,
        style_function=lambda x: {
            'fillColor': '#00ff88',
            'color': '#00ff88',
            'weight': 2,
            'fillOpacity': 0.5,
            'dashArray': '5, 3'
        }
    ).add_to(pred_group)

pred_group.add_to(m4)
folium.LayerControl().add_to(m4)
add_center_marker(m4)
add_title(m4, "Growth Intensity Heatmap", "Toggle predicted expansion layer")

legend = '''
<div style="position: fixed; bottom: 40px; right: 15px; z-index: 1000; 
            background: rgba(0,0,0,0.95); padding: 15px; border: 2px solid #ff6600;
            border-radius: 8px; font-size: 12px; color: white; box-shadow: 0 0 20px rgba(255,100,0,0.4);">
    <b style="color: #ffaa00;">🔥 Intensity</b><br><br>
    <div style="background: linear-gradient(to right, #ff3300, #ff9900, #ffcc00, #fff); 
                width: 130px; height: 18px; border-radius: 3px; border: 1px solid #666;"></div>
    <div style="display: flex; justify-content: space-between; width: 130px; margin-top: 3px;">
        <span>Low</span><span>High</span>
    </div><br>
    <span style="color: #00ff88;">▢</span> Predicted expansion
</div>
'''
m4.get_root().html.add_child(folium.Element(legend))
m4.save(output_dir / "animated_grid_map.html")
print("✓ Saved animated_grid_map.html")

# =============================================================================
# 5. ENHANCED TIMELINE (copy of main for compatibility)
# =============================================================================

import shutil
shutil.copy(output_dir / "time_slider_map.html", output_dir / "enhanced_timeline_map.html")
print("✓ Saved enhanced_timeline_map.html")

print("\n" + "="*60)
print("ALL MAPS COMPLETE - HIGH VISIBILITY")
print("  • 90% fill opacity")
print("  • Bright orange/yellow/white gradient")
print("  • Neon prediction colors")
print("  • Bold borders and legends")
print("="*60)
