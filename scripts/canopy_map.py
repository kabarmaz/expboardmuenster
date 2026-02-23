#!/usr/bin/env python3
"""
HIGH-VISIBILITY Canopy Loss & Prediction Map
Shows historical tree loss and future risk areas
"""

import geopandas as gpd
import pandas as pd
import numpy as np
import folium
from folium import plugins
from pathlib import Path

output_dir = Path("output/canopy_analysis")

print("Loading data...")

# Load canopy loss (historical)
loss_grid = gpd.read_file(output_dir / "canopy_loss_map.geojson")
loss_grid = loss_grid.to_crs(epsg=4326)
loss_cells = loss_grid[loss_grid['canopy_loss_ha'] > 0].copy()

# Load predictions (future risk)
pred_grid = gpd.read_file("output/growth_prediction/predicted_growth_areas.geojson")
pred_grid = pred_grid.to_crs(epsg=4326)

# Load forecast for summary stats
try:
    forecast = pd.read_csv(output_dir / "canopy_loss_forecast.csv")
except:
    forecast = None

print(f"Historical loss cells: {len(loss_cells)}")
print(f"Prediction cells: {len(pred_grid)}")

# Constants
CENTER_LAT, CENTER_LON = 51.9625, 7.6261
AVG_TREE_DENSITY = 400  # trees per hectare
AVG_CO2_PER_TREE = 21  # kg per year

# Calculate stats
total_historical_ha = loss_cells['canopy_loss_ha'].sum()
total_historical_trees = loss_cells['trees_lost'].sum()
total_historical_co2 = loss_cells['co2_loss_kg_yr'].sum() / 1000  # tonnes

# Estimate future loss from high-potential areas
high_risk = pred_grid[pred_grid['dev_potential'] > 0.4].copy()

# Canopy coverage varies by zone
CANOPY_RATES = {'0-3km': 0.15, '3-6km': 0.25, '6-10km': 0.35, '10-15km': 0.40, '15+km': 0.45}
high_risk['est_canopy_loss'] = high_risk.apply(
    lambda r: r['dev_potential'] * 0.25 * CANOPY_RATES.get(r['dist_zone'], 0.3), axis=1
)
high_risk['est_trees_lost'] = high_risk['est_canopy_loss'] * AVG_TREE_DENSITY
high_risk['est_co2_loss'] = high_risk['est_trees_lost'] * AVG_CO2_PER_TREE

total_future_ha = high_risk['est_canopy_loss'].sum()
total_future_trees = high_risk['est_trees_lost'].sum()
total_future_co2 = high_risk['est_co2_loss'].sum() / 1000

print(f"\nHistorical: {total_historical_ha:.1f} ha, {total_historical_trees:.0f} trees")
print(f"Future risk: {total_future_ha:.1f} ha, {total_future_trees:.0f} trees")

# =============================================================================
# CREATE THE MAP
# =============================================================================

m = folium.Map(
    location=[CENTER_LAT, CENTER_LON],
    zoom_start=11,
    tiles='cartodbdark_matter'
)

# =============================================================================
# LAYER 1: Historical Canopy Loss (Red/Orange gradient)
# =============================================================================

historical_group = folium.FeatureGroup(name='🌳 Historical Loss (2023-2025)', show=True)

max_loss = loss_cells['canopy_loss_ha'].quantile(0.95) if len(loss_cells) > 0 else 1

def get_loss_color(loss, max_val):
    """Red-orange gradient for historical loss"""
    if loss <= 0:
        return '#000000'
    ratio = min(loss / max_val, 1)
    # Orange to bright red to white
    if ratio < 0.5:
        r = 255
        g = int(180 - 100 * (ratio / 0.5))
        b = 0
    else:
        r = 255
        g = int(80 - 80 * ((ratio - 0.5) / 0.5))
        b = int(100 * ((ratio - 0.5) / 0.5))
    return f'#{r:02x}{g:02x}{b:02x}'

for _, row in loss_cells.iterrows():
    loss = row['canopy_loss_ha']
    trees = row['trees_lost']
    co2 = row['co2_loss_kg_yr']
    color = get_loss_color(loss, max_loss)
    
    popup_html = f"""
    <div style="font-family: Arial; background: #1a1a1a; color: white; 
                padding: 12px; border-radius: 8px; min-width: 180px;">
        <b style="color: #ff6600; font-size: 14px;">🌳 Historical Loss</b><br>
        <hr style="border-color: #444; margin: 8px 0;">
        <div style="margin: 4px 0;">🌲 <b>Canopy:</b> {loss:.3f} ha</div>
        <div style="margin: 4px 0;">🌳 <b>Trees:</b> ~{trees:.0f}</div>
        <div style="margin: 4px 0;">💨 <b>CO2:</b> {co2:.0f} kg/yr</div>
        <hr style="border-color: #444; margin: 8px 0;">
        <div style="font-size: 10px; color: #888;">
            Zone: {row['dist_zone']}<br>
            Direction: {row['direction']}
        </div>
    </div>
    """
    
    folium.GeoJson(
        row['geometry'].__geo_interface__,
        style_function=lambda x, c=color: {
            'fillColor': c,
            'color': '#ff4400',
            'weight': 1,
            'fillOpacity': 0.85
        },
        popup=folium.Popup(popup_html, max_width=220)
    ).add_to(historical_group)

historical_group.add_to(m)

# =============================================================================
# LAYER 2: Future Risk Areas (Green/Teal gradient)
# =============================================================================

future_group = folium.FeatureGroup(name='🔮 Future Risk (2026-2030)', show=True)

def get_risk_color(potential):
    """Green-teal gradient for future risk"""
    if potential <= 0.3:
        return '#004400'
    # Green to bright cyan
    ratio = (potential - 0.3) / 0.7
    r = 0
    g = int(150 + 105 * ratio)
    b = int(100 + 155 * ratio)
    return f'#{r:02x}{g:02x}{b:02x}'

for _, row in high_risk.iterrows():
    potential = row['dev_potential']
    est_trees = row['est_trees_lost']
    est_co2 = row['est_co2_loss']
    color = get_risk_color(potential)
    
    popup_html = f"""
    <div style="font-family: Arial; background: #1a1a1a; color: white; 
                padding: 12px; border-radius: 8px; min-width: 180px;">
        <b style="color: #00ff88; font-size: 14px;">🔮 Future Risk</b><br>
        <hr style="border-color: #444; margin: 8px 0;">
        <div style="margin: 4px 0;">📊 <b>Risk Level:</b> {potential*100:.0f}%</div>
        <div style="margin: 4px 0;">🌳 <b>Trees at Risk:</b> ~{est_trees:.0f}</div>
        <div style="margin: 4px 0;">💨 <b>CO2 at Risk:</b> {est_co2:.0f} kg/yr</div>
        <hr style="border-color: #444; margin: 8px 0;">
        <div style="font-size: 10px; color: #888;">
            Class: {row['potential_class']}<br>
            Zone: {row['dist_zone']}
        </div>
    </div>
    """
    
    folium.GeoJson(
        row['geometry'].__geo_interface__,
        style_function=lambda x, c=color, p=potential: {
            'fillColor': c,
            'color': '#00ff88',
            'weight': 1.5,
            'fillOpacity': 0.5 + 0.4 * p,
            'dashArray': '5, 3'
        },
        popup=folium.Popup(popup_html, max_width=220)
    ).add_to(future_group)

future_group.add_to(m)

# =============================================================================
# ADD CONTROLS AND MARKERS
# =============================================================================

# Layer control
folium.LayerControl(collapsed=False).add_to(m)

# City center marker
folium.CircleMarker(
    [CENTER_LAT, CENTER_LON],
    radius=12,
    color='#ffffff',
    fill=True,
    fillColor='#ffffff',
    fillOpacity=1.0,
    popup='<b>Münster City Center</b>'
).add_to(m)

# =============================================================================
# TITLE AND LEGEND
# =============================================================================

title_html = '''
<div style="position: fixed; top: 15px; left: 50%; transform: translateX(-50%); z-index: 1000; 
            background: linear-gradient(135deg, rgba(0,50,0,0.95), rgba(0,0,0,0.95)); 
            padding: 12px 30px; border-radius: 10px;
            font-size: 18px; color: white; text-align: center; 
            border: 2px solid #00aa44; box-shadow: 0 0 25px rgba(0,170,68,0.4);">
    <span style="font-size: 10px; color: #888; letter-spacing: 1px;">ANALYSIS OF SPATIO-TEMPORAL DATA</span><br>
    <b style="color: #44ff88;">🌳 Tree Canopy Impact Analysis</b><br>
    <span style="font-size: 12px; color: #aaa;">Historical Loss & Predicted Risk Areas</span>
</div>
'''
m.get_root().html.add_child(folium.Element(title_html))

# Legend and summary
legend_html = f'''
<div style="position: fixed; bottom: 30px; left: 20px; z-index: 1000; 
            background: rgba(0,0,0,0.95); padding: 18px; border: 2px solid #00aa44;
            border-radius: 10px; font-size: 12px; color: white; max-width: 260px;
            box-shadow: 0 0 20px rgba(0,170,68,0.3);">
    
    <b style="font-size: 15px; color: #44ff88;">📊 Canopy Impact Summary</b>
    <hr style="border-color: #444; margin: 10px 0;">
    
    <div style="margin-bottom: 12px;">
        <b style="color: #ff6600;">Historical (2023-2025):</b>
        <div style="background: linear-gradient(to right, #ff8800, #ff4400, #ff2200); 
                    height: 12px; margin: 5px 0; border-radius: 3px;"></div>
        <div style="display: flex; justify-content: space-between; font-size: 11px; color: #aaa;">
            <span>Low loss</span><span>High loss</span>
        </div>
        <div style="margin-top: 8px; padding: 8px; background: rgba(255,100,0,0.2); border-radius: 5px;">
            🌲 <b>{total_historical_ha:.1f} ha</b> canopy lost<br>
            🌳 <b>~{total_historical_trees:,.0f}</b> trees removed<br>
            💨 <b>{total_historical_co2:.1f} t/yr</b> CO2 impact
        </div>
    </div>
    
    <div>
        <b style="color: #00ff88;">Predicted Risk (2026-2030):</b>
        <div style="background: linear-gradient(to right, #004400, #00cc88, #00ffff); 
                    height: 12px; margin: 5px 0; border-radius: 3px; border: 1px dashed #00ff88;"></div>
        <div style="display: flex; justify-content: space-between; font-size: 11px; color: #aaa;">
            <span>Low risk</span><span>High risk</span>
        </div>
        <div style="margin-top: 8px; padding: 8px; background: rgba(0,255,136,0.15); border-radius: 5px;">
            🌲 <b>{total_future_ha:.1f} ha</b> at risk<br>
            🌳 <b>~{total_future_trees:,.0f}</b> trees threatened<br>
            💨 <b>{total_future_co2:.1f} t/yr</b> potential CO2 loss
        </div>
    </div>
    
    <hr style="border-color: #444; margin: 12px 0;">
    <div style="text-align: center; color: #888; font-size: 10px;">
        Toggle layers with control (top-right)<br>
        Click any cell for details
    </div>
</div>
'''
m.get_root().html.add_child(folium.Element(legend_html))

# Environmental impact panel (right side)
impact_html = f'''
<div style="position: fixed; bottom: 30px; right: 20px; z-index: 1000; 
            background: rgba(0,0,0,0.95); padding: 18px; border: 2px solid #ff6600;
            border-radius: 10px; font-size: 12px; color: white; max-width: 220px;
            box-shadow: 0 0 20px rgba(255,100,0,0.3);">
    
    <b style="font-size: 14px; color: #ff9900;">🌍 Environmental Impact</b>
    <hr style="border-color: #444; margin: 10px 0;">
    
    <div style="margin: 8px 0;">
        <b style="color: #ff6600;">Combined Total:</b>
    </div>
    
    <div style="font-size: 20px; text-align: center; margin: 10px 0; color: #ffcc00;">
        ~{total_historical_trees + total_future_trees:,.0f}
    </div>
    <div style="text-align: center; font-size: 11px; color: #aaa;">trees affected</div>
    
    <hr style="border-color: #333; margin: 10px 0;">
    
    <div style="font-size: 11px; line-height: 1.8;">
        🚗 Equal to <b style="color: #ffaa00;">{(total_historical_co2 + total_future_co2) / 4.6:.0f}</b> cars/year<br>
        ✈️ Or <b style="color: #ffaa00;">{(total_historical_co2 + total_future_co2) / 0.9:.0f}</b> transatlantic flights<br>
        🏠 Or heating <b style="color: #ffaa00;">{(total_historical_co2 + total_future_co2) / 2.5:.0f}</b> homes/year
    </div>
</div>
'''
m.get_root().html.add_child(folium.Element(impact_html))

# Save
m.save(output_dir / "canopy_loss_map.html")
print(f"\n✓ Saved: {output_dir / 'canopy_loss_map.html'}")
print("Open in browser - use layer control to toggle historical vs predicted!")
