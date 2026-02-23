#!/usr/bin/env python3
"""
Tree Canopy Loss Estimation and Forecasting
Estimates canopy loss due to urban development in Münster
"""

import geopandas as gpd
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
from pathlib import Path
import warnings
warnings.filterwarnings('ignore')

# Setup
output_dir = Path("output/canopy_analysis")
output_dir.mkdir(parents=True, exist_ok=True)

print("=" * 60)
print("TREE CANOPY LOSS ESTIMATION")
print("=" * 60)

# ============================================================
# ASSUMPTIONS AND PARAMETERS
# ============================================================
# Based on typical urban development patterns and Münster's characteristics

# Average building footprint (m²)
AVG_BUILDING_FOOTPRINT = 150  # Conservative estimate for mixed residential/commercial

# Canopy coverage assumptions
# In suburban areas, ~30-40% of undeveloped land has tree canopy
# In peri-urban areas, ~50-60% has vegetation/trees
# Development typically requires clearing 1.5-2x the building footprint
# (accounting for access roads, parking, setbacks)

DEVELOPMENT_MULTIPLIER = 1.8  # Total land disturbed per building footprint
CANOPY_COVERAGE_BY_ZONE = {
    '0-3km': 0.15,      # Urban core - less canopy
    '3-6km': 0.25,      # Inner suburbs
    '6-10km': 0.35,     # Outer suburbs
    '10-15km': 0.45,    # Peri-urban
    '15+km': 0.55       # Rural fringe - most canopy
}

# Average tree parameters for carbon/volume estimation
AVG_TREE_DENSITY_PER_HA = 80  # Trees per hectare of canopy
AVG_TREE_HEIGHT_M = 12
AVG_TREE_CROWN_DIAMETER_M = 6
AVG_TREE_AGE_YEARS = 25

# Carbon sequestration (kg CO2 per tree per year)
CO2_PER_TREE_PER_YEAR = 22  # Average mature urban tree

print("\nParameters:")
print(f"  Avg building footprint: {AVG_BUILDING_FOOTPRINT} m²")
print(f"  Development multiplier: {DEVELOPMENT_MULTIPLIER}x")
print(f"  Avg tree density: {AVG_TREE_DENSITY_PER_HA} trees/ha canopy")
print(f"  CO2 sequestration: {CO2_PER_TREE_PER_YEAR} kg/tree/year")

# ============================================================
print("\n" + "=" * 60)
print("1. LOADING DATA")
print("=" * 60)

# Load growth data
grid = gpd.read_file("output/spatial_stats/grid_with_direction.geojson")
grid = grid.to_crs(epsg=25832)

# Load prediction data
predictions = gpd.read_file("output/growth_prediction/predicted_growth_areas.geojson")
predictions = predictions.to_crs(epsg=25832)

# Get period columns
period_cols = [c for c in grid.columns if c.startswith('new_')]
period_cols = sorted(period_cols)

# Calculate totals
grid['total_new'] = grid[period_cols].sum(axis=1)

# Create distance zones
grid['dist_zone'] = pd.cut(grid['distance_km'], 
                            bins=[0, 3, 6, 10, 15, 25],
                            labels=['0-3km', '3-6km', '6-10km', '10-15km', '15+km'])

print(f"Loaded {len(grid)} grid cells")
print(f"Total new buildings (2023-2025): {grid['total_new'].sum():.0f}")

# ============================================================
print("\n" + "=" * 60)
print("2. HISTORICAL CANOPY LOSS ESTIMATION")
print("=" * 60)

# Calculate canopy loss per cell
def estimate_canopy_loss(row):
    zone = row['dist_zone']
    new_buildings = row['total_new']
    
    if pd.isna(zone) or new_buildings == 0:
        return 0, 0, 0, 0
    
    # Total land disturbed (m²)
    land_disturbed = new_buildings * AVG_BUILDING_FOOTPRINT * DEVELOPMENT_MULTIPLIER
    
    # Canopy coverage in this zone
    canopy_pct = CANOPY_COVERAGE_BY_ZONE.get(zone, 0.3)
    
    # Estimated canopy lost (m²)
    canopy_lost_m2 = land_disturbed * canopy_pct
    
    # Convert to hectares
    canopy_lost_ha = canopy_lost_m2 / 10000
    
    # Estimated trees lost
    trees_lost = canopy_lost_ha * AVG_TREE_DENSITY_PER_HA
    
    # Annual CO2 sequestration lost (kg/year)
    co2_lost = trees_lost * CO2_PER_TREE_PER_YEAR
    
    return canopy_lost_m2, canopy_lost_ha, trees_lost, co2_lost

# Apply to all cells
results = grid.apply(estimate_canopy_loss, axis=1, result_type='expand')
grid['canopy_loss_m2'] = results[0]
grid['canopy_loss_ha'] = results[1]
grid['trees_lost'] = results[2]
grid['co2_loss_kg_yr'] = results[3]

# Summary by period
print("\nCanopy Loss by Time Period:")
period_loss = []
for period in period_cols:
    period_date = period.replace('new_', '')
    buildings = grid[period].sum()
    
    # Apply same calculation
    loss = buildings * AVG_BUILDING_FOOTPRINT * DEVELOPMENT_MULTIPLIER
    avg_canopy_pct = 0.35  # Average across zones
    canopy_m2 = loss * avg_canopy_pct
    canopy_ha = canopy_m2 / 10000
    trees = canopy_ha * AVG_TREE_DENSITY_PER_HA
    co2 = trees * CO2_PER_TREE_PER_YEAR
    
    period_loss.append({
        'period': period_date,
        'new_buildings': buildings,
        'land_disturbed_ha': loss / 10000,
        'canopy_loss_ha': canopy_ha,
        'trees_lost': trees,
        'co2_loss_kg_yr': co2
    })
    print(f"  {period_date}: {buildings:.0f} buildings → {canopy_ha:.2f} ha canopy, ~{trees:.0f} trees")

period_df = pd.DataFrame(period_loss)
period_df.to_csv(output_dir / "canopy_loss_by_period.csv", index=False)

# Total historical loss
total_canopy_ha = grid['canopy_loss_ha'].sum()
total_trees = grid['trees_lost'].sum()
total_co2 = grid['co2_loss_kg_yr'].sum()

print(f"\nTOTAL HISTORICAL LOSS (2023-2025):")
print(f"  Canopy area: {total_canopy_ha:.1f} hectares ({total_canopy_ha*10000:.0f} m²)")
print(f"  Trees lost: ~{total_trees:.0f}")
print(f"  CO2 sequestration lost: {total_co2/1000:.1f} tonnes/year")

# By zone
print("\nCanopy Loss by Distance Zone:")
zone_summary = grid.groupby('dist_zone').agg({
    'total_new': 'sum',
    'canopy_loss_ha': 'sum',
    'trees_lost': 'sum',
    'co2_loss_kg_yr': 'sum'
}).round(2)
print(zone_summary.to_string())

# ============================================================
print("\n" + "=" * 60)
print("3. FUTURE CANOPY LOSS FORECAST")
print("=" * 60)

# Load forecast data
forecast_df = pd.read_csv("output/forecasting/forecasts.csv")
print(f"\nForecast periods: {len(forecast_df)}")

# Project canopy loss for each forecast period
future_loss = []
for _, row in forecast_df.iterrows():
    buildings = max(row['ensemble'], 0)  # Ensure non-negative
    
    # Calculate loss with same methodology
    loss = buildings * AVG_BUILDING_FOOTPRINT * DEVELOPMENT_MULTIPLIER
    avg_canopy_pct = 0.38  # Slightly higher - growth moving outward
    canopy_ha = (loss * avg_canopy_pct) / 10000
    trees = canopy_ha * AVG_TREE_DENSITY_PER_HA
    co2 = trees * CO2_PER_TREE_PER_YEAR
    
    future_loss.append({
        'period': row['date'],
        'predicted_buildings': buildings,
        'canopy_loss_ha': canopy_ha,
        'trees_lost': trees,
        'co2_loss_kg_yr': co2
    })
    print(f"  {row['date']}: ~{buildings:.0f} buildings → {canopy_ha:.2f} ha canopy, ~{trees:.0f} trees")

future_df = pd.DataFrame(future_loss)
future_df.to_csv(output_dir / "canopy_loss_forecast.csv", index=False)

# Extended 5-year forecast (2025-2030)
avg_buildings_per_period = future_df['predicted_buildings'].mean()
periods_to_2030 = 10  # 5 years × 2 periods/year

total_future_buildings = avg_buildings_per_period * periods_to_2030
total_future_canopy_ha = (total_future_buildings * AVG_BUILDING_FOOTPRINT * 
                           DEVELOPMENT_MULTIPLIER * 0.38) / 10000
total_future_trees = total_future_canopy_ha * AVG_TREE_DENSITY_PER_HA
total_future_co2 = total_future_trees * CO2_PER_TREE_PER_YEAR

print(f"\n5-YEAR FORECAST (2025-2030):")
print(f"  Predicted new buildings: ~{total_future_buildings:.0f}")
print(f"  Projected canopy loss: {total_future_canopy_ha:.1f} hectares")
print(f"  Projected trees lost: ~{total_future_trees:.0f}")
print(f"  Projected CO2 sequestration lost: {total_future_co2/1000:.1f} tonnes/year")

# Spatial forecast - where will loss occur?
print("\nPredicted Canopy Loss by Direction (based on development potential):")
if 'direction' in predictions.columns:
    predictions['predicted_canopy_loss_ha'] = (
        predictions['dev_potential'] * 10 *  # Scaling factor
        CANOPY_COVERAGE_BY_ZONE.get('6-10km', 0.35)
    )
    dir_forecast = predictions.groupby('direction')['predicted_canopy_loss_ha'].sum()
    print(dir_forecast.sort_values(ascending=False).to_string())

# ============================================================
print("\n" + "=" * 60)
print("4. CREATING VISUALIZATIONS")
print("=" * 60)

# Custom green colormap for canopy
colors_green = ['#f7fcf5', '#c7e9c0', '#74c476', '#31a354', '#006d2c']
cmap_green = LinearSegmentedColormap.from_list('canopy', colors_green)
colors_red = ['#fff5f0', '#fcbba1', '#fb6a4a', '#cb181d', '#67000d']
cmap_red = LinearSegmentedColormap.from_list('loss', colors_red)

fig = plt.figure(figsize=(18, 14))

# Create grid layout
gs = fig.add_gridspec(3, 3, hspace=0.3, wspace=0.25)

# Plot 1: Canopy Loss Map (Historical)
ax1 = fig.add_subplot(gs[0, 0])
grid.plot(ax=ax1, column='canopy_loss_ha', cmap=cmap_red, legend=True,
          legend_kwds={'label': 'Canopy Loss (ha)', 'shrink': 0.6},
          edgecolor='white', linewidth=0.2)
ax1.set_title('Historical Canopy Loss\n(2023-2025)', fontsize=11)
ax1.set_axis_off()

# Plot 2: Trees Lost Map
ax2 = fig.add_subplot(gs[0, 1])
grid.plot(ax=ax2, column='trees_lost', cmap='YlOrBr', legend=True,
          legend_kwds={'label': 'Trees Lost', 'shrink': 0.6},
          edgecolor='white', linewidth=0.2)
ax2.set_title('Estimated Trees Lost\n(2023-2025)', fontsize=11)
ax2.set_axis_off()

# Plot 3: CO2 Loss Map
ax3 = fig.add_subplot(gs[0, 2])
grid['co2_loss_tonnes'] = grid['co2_loss_kg_yr'] / 1000
grid.plot(ax=ax3, column='co2_loss_tonnes', cmap='Reds', legend=True,
          legend_kwds={'label': 'CO2 Loss (tonnes/yr)', 'shrink': 0.6},
          edgecolor='white', linewidth=0.2)
ax3.set_title('Annual CO2 Sequestration Lost\n(tonnes/year)', fontsize=11)
ax3.set_axis_off()

# Plot 4: Time Series of Canopy Loss
ax4 = fig.add_subplot(gs[1, 0])
dates = pd.to_datetime(period_df['period'])
ax4.bar(dates, period_df['canopy_loss_ha'], color='#31a354', edgecolor='darkgreen', 
        width=150, label='Historical')
# Add forecast
future_dates = pd.to_datetime(future_df['period'])
ax4.bar(future_dates, future_df['canopy_loss_ha'], color='#fb6a4a', edgecolor='darkred',
        width=150, alpha=0.7, label='Forecast')
ax4.axvline(dates.max(), color='gray', linestyle='--', alpha=0.5)
ax4.set_xlabel('Date')
ax4.set_ylabel('Canopy Loss (hectares)')
ax4.set_title('Canopy Loss Over Time', fontsize=11)
ax4.legend()
ax4.grid(True, alpha=0.3)

# Plot 5: Cumulative Canopy Loss
ax5 = fig.add_subplot(gs[1, 1])
cumulative_hist = period_df['canopy_loss_ha'].cumsum()
cumulative_future = cumulative_hist.iloc[-1] + future_df['canopy_loss_ha'].cumsum()
ax5.plot(dates, cumulative_hist, 'g-o', label='Historical', markersize=6)
ax5.plot(future_dates, cumulative_future, 'r--o', label='Projected', markersize=6)
ax5.fill_between(dates, 0, cumulative_hist, color='green', alpha=0.2)
ax5.fill_between(future_dates, cumulative_hist.iloc[-1], cumulative_future, color='red', alpha=0.2)
ax5.axvline(dates.max(), color='gray', linestyle='--', alpha=0.5)
ax5.set_xlabel('Date')
ax5.set_ylabel('Cumulative Canopy Loss (ha)')
ax5.set_title('Cumulative Canopy Loss', fontsize=11)
ax5.legend()
ax5.grid(True, alpha=0.3)

# Plot 6: Trees & CO2 Loss by Zone (stacked bar)
ax6 = fig.add_subplot(gs[1, 2])
zones = zone_summary.index.tolist()
trees = zone_summary['trees_lost'].values
x = np.arange(len(zones))
bars = ax6.bar(x, trees, color=['#a1dab4', '#41b6c4', '#2c7fb8', '#253494', '#081d58'])
ax6.set_xticks(x)
ax6.set_xticklabels(zones, rotation=45)
ax6.set_xlabel('Distance from City Center')
ax6.set_ylabel('Trees Lost')
ax6.set_title('Trees Lost by Zone', fontsize=11)
ax6.grid(True, alpha=0.3, axis='y')
# Add value labels
for bar, val in zip(bars, trees):
    ax6.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 5, 
             f'{val:.0f}', ha='center', va='bottom', fontsize=9)

# Plot 7: Volume visualization - 3D-like tree representation
ax7 = fig.add_subplot(gs[2, 0])
# Create a visual representation of tree volume lost
total_volume = total_trees * (np.pi * (AVG_TREE_CROWN_DIAMETER_M/2)**2 * AVG_TREE_HEIGHT_M) / 3
# Represent as stacked circles
n_stacks = 5
for i in range(n_stacks):
    circle = plt.Circle((0.5, 0.1 + i*0.18), 0.15 - i*0.02, 
                         color=plt.cm.Greens(0.3 + i*0.15), alpha=0.8)
    ax7.add_patch(circle)
ax7.set_xlim(0, 1)
ax7.set_ylim(0, 1)
ax7.set_aspect('equal')
ax7.text(0.5, 0.95, f'~{total_trees:.0f} Trees Lost', ha='center', fontsize=14, fontweight='bold')
ax7.text(0.5, 0.02, f'Est. Crown Volume: {total_volume/1000:.0f}k m³', ha='center', fontsize=10)
ax7.set_title('Tree Volume Impact\n(Visualization)', fontsize=11)
ax7.axis('off')

# Plot 8: Environmental Impact Summary
ax8 = fig.add_subplot(gs[2, 1])
ax8.axis('off')
summary_text = f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  ENVIRONMENTAL IMPACT SUMMARY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  HISTORICAL (2023-2025)
  ─────────────────────
  🌳 Trees Lost: ~{total_trees:,.0f}
  🌲 Canopy Area: {total_canopy_ha:.1f} ha
  💨 CO2 Impact: {total_co2/1000:.1f} t/year

  FORECAST (2025-2030)
  ─────────────────────
  🌳 Trees at Risk: ~{total_future_trees:,.0f}
  🌲 Canopy at Risk: {total_future_canopy_ha:.1f} ha
  💨 CO2 Impact: {total_future_co2/1000:.1f} t/year

  TOTAL IMPACT
  ─────────────────────
  🌳 Total Trees: ~{total_trees + total_future_trees:,.0f}
  🌲 Total Canopy: {total_canopy_ha + total_future_canopy_ha:.1f} ha
  💨 Total CO2: {(total_co2 + total_future_co2)/1000:.1f} t/year
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
ax8.text(0.5, 0.5, summary_text, ha='center', va='center', fontsize=10,
         family='monospace', bbox=dict(boxstyle='round', facecolor='#f0fff0', alpha=0.8))

# Plot 9: Future Risk Areas Map
ax9 = fig.add_subplot(gs[2, 2])
grid.plot(ax=ax9, color='#f0f0f0', edgecolor='white', linewidth=0.2)
# Highlight high-risk areas
if 'dev_potential' in predictions.columns:
    predictions['future_canopy_risk'] = predictions['dev_potential'] * CANOPY_COVERAGE_BY_ZONE.get('6-10km', 0.35)
    high_risk = predictions[predictions['dev_potential'] > 0.4]
    high_risk.plot(ax=ax9, column='future_canopy_risk', cmap=cmap_red,
                   legend=True, legend_kwds={'label': 'Risk Level', 'shrink': 0.5},
                   edgecolor='white', linewidth=0.3)
ax9.set_title('Predicted Canopy Loss Zones\n(2025-2030)', fontsize=11)
ax9.set_axis_off()

plt.suptitle('🌳 Münster Urban Expansion: Tree Canopy Impact Analysis', 
             fontsize=16, fontweight='bold', y=0.98)
plt.savefig(output_dir / "canopy_loss_analysis.png", dpi=150, bbox_inches='tight', facecolor='white')
print(f"  Saved: {output_dir / 'canopy_loss_analysis.png'}")

# ============================================================
# Additional: Volume/3D Impact Visualization
fig2, axes = plt.subplots(1, 3, figsize=(16, 5))

# Comparison bars - Historical vs Forecast
ax1 = axes[0]
categories = ['Historical\n(2023-2025)', 'Forecast\n(2025-2030)']
trees_vals = [total_trees, total_future_trees]
colors = ['#31a354', '#fb6a4a']
bars = ax1.bar(categories, trees_vals, color=colors, edgecolor='black', linewidth=1.5)
ax1.set_ylabel('Estimated Trees Lost', fontsize=12)
ax1.set_title('Tree Loss Comparison', fontsize=12)
for bar, val in zip(bars, trees_vals):
    ax1.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 20, 
             f'{val:,.0f}', ha='center', fontsize=11, fontweight='bold')
ax1.grid(True, alpha=0.3, axis='y')

# CO2 impact equivalent
ax2 = axes[1]
total_co2_tonnes = (total_co2 + total_future_co2) / 1000
cars_equivalent = total_co2_tonnes / 4.6  # Avg car emits 4.6 tonnes CO2/year
flights_equivalent = total_co2_tonnes / 0.9  # Avg transatlantic flight ~0.9 tonnes

labels = ['Annual CO2\nLost (tonnes)', 'Equivalent Cars\n(per year)', 'Transatlantic\nFlights']
values = [total_co2_tonnes, cars_equivalent, flights_equivalent]
colors2 = ['#e41a1c', '#377eb8', '#4daf4a']
bars2 = ax2.bar(labels, values, color=colors2, edgecolor='black')
ax2.set_ylabel('Equivalent Impact', fontsize=12)
ax2.set_title('CO2 Sequestration Loss Equivalents', fontsize=12)
for bar, val in zip(bars2, values):
    ax2.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 5, 
             f'{val:,.0f}', ha='center', fontsize=10, fontweight='bold')
ax2.grid(True, alpha=0.3, axis='y')

# Canopy area comparison
ax3 = axes[2]
# Compare to known areas
total_canopy = total_canopy_ha + total_future_canopy_ha
football_fields = total_canopy / 0.71  # FIFA football field ~0.71 ha
aasee = 40.2  # Aasee lake in Münster ~40 ha
aasee_ratio = total_canopy / aasee

labels3 = [f'Total Canopy\nLoss ({total_canopy:.1f} ha)', 
           f'Football Fields\n({football_fields:.0f})', 
           f'× Aasee Lake\n({aasee_ratio:.1f}x)']
values3 = [total_canopy, football_fields * 0.71, aasee_ratio * aasee]
colors3 = ['#228b22', '#ffa500', '#1e90ff']
bars3 = ax3.bar(labels3, values3, color=colors3, edgecolor='black')
ax3.set_ylabel('Hectares', fontsize=12)
ax3.set_title('Canopy Loss: Size Comparison', fontsize=12)
ax3.grid(True, alpha=0.3, axis='y')

plt.tight_layout()
plt.savefig(output_dir / "canopy_impact_comparison.png", dpi=150, bbox_inches='tight', facecolor='white')
print(f"  Saved: {output_dir / 'canopy_impact_comparison.png'}")

# ============================================================
print("\n" + "=" * 60)
print("5. EXPORTING DATA")
print("=" * 60)

# Export grid with canopy data
grid_export = grid.drop(columns=['geometry']).copy() if 'geometry' in grid.columns else grid.copy()
grid_export[['cell_id', 'direction', 'distance_km', 'dist_zone', 'total_new',
             'canopy_loss_ha', 'trees_lost', 'co2_loss_kg_yr']].to_csv(
    output_dir / "canopy_loss_by_cell.csv", index=False)
print(f"  Saved: {output_dir / 'canopy_loss_by_cell.csv'}")

# Export summary
summary = {
    'analysis_period_historical': '2023-2025',
    'forecast_period': '2025-2030',
    'historical_buildings': int(grid['total_new'].sum()),
    'historical_canopy_loss_ha': float(total_canopy_ha),
    'historical_trees_lost': float(total_trees),
    'historical_co2_loss_tonnes_yr': float(total_co2/1000),
    'forecast_buildings': float(total_future_buildings),
    'forecast_canopy_loss_ha': float(total_future_canopy_ha),
    'forecast_trees_lost': float(total_future_trees),
    'forecast_co2_loss_tonnes_yr': float(total_future_co2/1000),
    'total_canopy_loss_ha': float(total_canopy_ha + total_future_canopy_ha),
    'total_trees_lost': float(total_trees + total_future_trees),
    'total_co2_loss_tonnes_yr': float((total_co2 + total_future_co2)/1000),
    'equivalent_cars_per_year': float(cars_equivalent),
    'equivalent_football_fields': float(football_fields)
}
pd.DataFrame([summary]).to_csv(output_dir / "canopy_analysis_summary.csv", index=False)
print(f"  Saved: {output_dir / 'canopy_analysis_summary.csv'}")

# Export spatial data
grid_geo = grid.to_crs(epsg=4326)
grid_geo[['cell_id', 'canopy_loss_ha', 'trees_lost', 'co2_loss_kg_yr', 'geometry']].to_file(
    output_dir / "canopy_loss_map.geojson", driver='GeoJSON')
print(f"  Saved: {output_dir / 'canopy_loss_map.geojson'}")

print("\n" + "=" * 60)
print("CANOPY ANALYSIS COMPLETE")
print("=" * 60)
print(f"""
📊 KEY FINDINGS:

Historical Impact (2023-2025):
  • {total_canopy_ha:.1f} hectares of canopy lost
  • ~{total_trees:,.0f} trees removed
  • {total_co2/1000:.1f} tonnes CO2/year sequestration lost

Projected Impact (2025-2030):
  • {total_future_canopy_ha:.1f} hectares at risk
  • ~{total_future_trees:,.0f} additional trees at risk
  • {total_future_co2/1000:.1f} tonnes CO2/year additional loss

Total Environmental Cost:
  • {total_canopy_ha + total_future_canopy_ha:.1f} ha canopy ({football_fields:.0f} football fields)
  • Equivalent to removing {cars_equivalent:.0f} cars from roads
  • Greatest impact in {zone_summary['canopy_loss_ha'].idxmax()} zone
""")
