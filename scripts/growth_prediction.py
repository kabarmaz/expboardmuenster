#!/usr/bin/env python3
"""
Areal Growth Visualization and Prediction
Identifies and visualizes areas predicted to have future development
"""

import geopandas as gpd
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
from pathlib import Path
from scipy import ndimage
import warnings
warnings.filterwarnings('ignore')

# Setup
output_dir = Path("output/growth_prediction")
output_dir.mkdir(parents=True, exist_ok=True)

print("Loading data...")
grid = gpd.read_file("output/spatial_stats/grid_with_direction.geojson")
grid = grid.to_crs(epsg=25832)

# Get period columns
period_cols = [c for c in grid.columns if c.startswith('new_')]
period_cols = sorted(period_cols)

print(f"Found {len(period_cols)} periods: {[c.replace('new_', '') for c in period_cols]}")

# Calculate total and recent growth
grid['total_new'] = grid[period_cols].sum(axis=1)

# Split into early vs recent periods
mid_point = len(period_cols) // 2
early_cols = period_cols[:mid_point]
recent_cols = period_cols[mid_point:]

grid['early_growth'] = grid[early_cols].sum(axis=1)
grid['recent_growth'] = grid[recent_cols].sum(axis=1)

# ============================================================
print("\n" + "=" * 60)
print("1. GROWTH TREND ANALYSIS BY CELL")
print("=" * 60)

# Calculate growth trend (accelerating vs decelerating)
def calc_trend(row):
    values = [row[c] for c in period_cols]
    if sum(values) == 0:
        return 0
    x = np.arange(len(values))
    try:
        slope, _ = np.polyfit(x, values, 1)
        return slope
    except:
        return 0

grid['growth_trend'] = grid.apply(calc_trend, axis=1)

# Classify trend
def classify_trend(trend, total):
    if total == 0:
        return 'No Growth'
    elif trend > 0.5:
        return 'Accelerating'
    elif trend < -0.5:
        return 'Decelerating'
    else:
        return 'Stable'

grid['trend_class'] = grid.apply(lambda r: classify_trend(r['growth_trend'], r['total_new']), axis=1)

trend_counts = grid['trend_class'].value_counts()
print("\nGrowth Trend Distribution:")
print(trend_counts.to_string())

# ============================================================
print("\n" + "=" * 60)
print("2. DEVELOPMENT POTENTIAL SCORING")
print("=" * 60)

# Create a development potential score based on multiple factors
# 1. Recent growth activity (higher = more likely to continue)
# 2. Neighbor growth (spatial spillover effect)
# 3. Growth trend (accelerating areas)
# 4. Distance from center (suburban frontier)

# Normalize recent growth
max_recent = grid['recent_growth'].quantile(0.95)
grid['score_recent'] = np.minimum(grid['recent_growth'] / max(max_recent, 1), 1)

# Calculate neighbor growth using spatial weights
from libpysal.weights import Queen
try:
    w = Queen.from_dataframe(grid, use_index=False)
    # Neighbor average growth
    neighbor_growth = []
    for i in range(len(grid)):
        neighbors = w.neighbors.get(i, [])
        if neighbors:
            neighbor_vals = grid.iloc[neighbors]['recent_growth'].mean()
        else:
            neighbor_vals = 0
        neighbor_growth.append(neighbor_vals)
    grid['neighbor_growth'] = neighbor_growth
    max_neighbor = grid['neighbor_growth'].quantile(0.95)
    grid['score_neighbor'] = np.minimum(grid['neighbor_growth'] / max(max_neighbor, 1), 1)
except Exception as e:
    print(f"  Spatial weights error: {e}")
    grid['score_neighbor'] = 0

# Normalize trend (focus on positive/accelerating)
grid['score_trend'] = np.clip(grid['growth_trend'] / 2, 0, 1)

# Distance factor - growth often happens in suburban ring
# Weight mid-distance areas higher (2-10km)
def distance_weight(d):
    if d < 2:
        return 0.3  # City center - less space
    elif d < 6:
        return 1.0  # Inner suburbs - high potential
    elif d < 10:
        return 0.8  # Outer suburbs
    else:
        return 0.4  # Rural fringe

grid['score_distance'] = grid['distance_km'].apply(distance_weight)

# Combined development potential score
grid['dev_potential'] = (
    0.35 * grid['score_recent'] +      # Recent activity is strong signal
    0.30 * grid['score_neighbor'] +    # Spatial spillover
    0.20 * grid['score_trend'] +       # Acceleration bonus
    0.15 * grid['score_distance']      # Location factor
)

# Identify high-potential areas
threshold = grid['dev_potential'].quantile(0.75)
grid['high_potential'] = grid['dev_potential'] > threshold

print(f"\nDevelopment Potential Score Statistics:")
print(f"  Mean: {grid['dev_potential'].mean():.3f}")
print(f"  Median: {grid['dev_potential'].median():.3f}")
print(f"  Max: {grid['dev_potential'].max():.3f}")
print(f"  High potential cells (>75th pctl): {grid['high_potential'].sum()}")

# Classify development zones
def classify_potential(score):
    if score >= 0.6:
        return 'Very High (Rapid Development Expected)'
    elif score >= 0.4:
        return 'High (Likely Development)'
    elif score >= 0.2:
        return 'Moderate (Possible Development)'
    else:
        return 'Low (Stable/No Development)'

grid['potential_class'] = grid['dev_potential'].apply(classify_potential)

potential_counts = grid['potential_class'].value_counts()
print("\nDevelopment Potential Classification:")
print(potential_counts.to_string())

# ============================================================
print("\n" + "=" * 60)
print("3. PREDICTED GROWTH AREAS")
print("=" * 60)

# Predict future growth based on potential score
# Estimate buildings based on historical relationship
high_pot = grid[grid['dev_potential'] > 0.4]
print(f"\nAreas with High/Very High development potential:")
print(f"  Number of cells: {len(high_pot)}")
print(f"  Total area: {len(high_pot) * 0.25:.1f} km² (500m grid)")

# Estimate future buildings
avg_buildings_high_pot = high_pot['recent_growth'].mean()
predicted_per_period = len(high_pot) * avg_buildings_high_pot * 0.5  # Conservative estimate
print(f"  Estimated new buildings/period: ~{predicted_per_period:.0f}")

# By direction
high_pot_by_dir = high_pot.groupby('direction').agg({
    'dev_potential': 'mean',
    'cell_id': 'count'
}).rename(columns={'cell_id': 'count'}).sort_values('count', ascending=False)
print(f"\nHigh-potential areas by direction:")
print(high_pot_by_dir.to_string())

# By distance zone
grid['dist_zone'] = pd.cut(grid['distance_km'], 
                            bins=[0, 3, 6, 10, 15, 25],
                            labels=['0-3km', '3-6km', '6-10km', '10-15km', '15+km'])
zone_potential = grid.groupby('dist_zone').agg({
    'dev_potential': 'mean',
    'high_potential': 'sum',
    'total_new': 'sum'
})
print(f"\nDevelopment potential by distance zone:")
print(zone_potential.to_string())

# ============================================================
print("\n" + "=" * 60)
print("4. CREATING VISUALIZATIONS")
print("=" * 60)

# Custom colormap for development potential
colors_pot = ['#f0f0f0', '#ffffb2', '#fecc5c', '#fd8d3c', '#e31a1c']
cmap_pot = LinearSegmentedColormap.from_list('dev_potential', colors_pot)

fig, axes = plt.subplots(2, 2, figsize=(16, 14))

# Plot 1: Historical Growth (Total)
ax1 = axes[0, 0]
grid.plot(ax=ax1, column='total_new', cmap='YlOrRd', legend=True,
          legend_kwds={'label': 'New Buildings', 'shrink': 0.6},
          edgecolor='white', linewidth=0.3)
ax1.set_title('Historical Growth (2023-2025)\nNew Buildings per Grid Cell', fontsize=12)
ax1.set_axis_off()

# Plot 2: Recent vs Early Growth Shift
ax2 = axes[0, 1]
# Calculate shift: positive = more recent growth
grid['growth_shift'] = grid['recent_growth'] - grid['early_growth']
vmax = max(abs(grid['growth_shift'].quantile(0.05)), abs(grid['growth_shift'].quantile(0.95)))
grid.plot(ax=ax2, column='growth_shift', cmap='RdBu_r', legend=True,
          legend_kwds={'label': 'Growth Shift (Recent - Early)', 'shrink': 0.6},
          vmin=-vmax, vmax=vmax,
          edgecolor='white', linewidth=0.3)
ax2.set_title('Growth Shift\nRed = More Recent Growth, Blue = More Early Growth', fontsize=12)
ax2.set_axis_off()

# Plot 3: Development Potential Score
ax3 = axes[1, 0]
grid.plot(ax=ax3, column='dev_potential', cmap=cmap_pot, legend=True,
          legend_kwds={'label': 'Development Potential Score', 'shrink': 0.6},
          vmin=0, vmax=grid['dev_potential'].quantile(0.95),
          edgecolor='white', linewidth=0.3)
ax3.set_title('Development Potential Score\nHigher = More Likely Future Growth', fontsize=12)
ax3.set_axis_off()

# Plot 4: Predicted High-Growth Areas
ax4 = axes[1, 1]
# Background - all cells
grid.plot(ax=ax4, color='#f0f0f0', edgecolor='white', linewidth=0.3)
# Highlight high potential
pot_colors = {
    'Very High (Rapid Development Expected)': '#e31a1c',
    'High (Likely Development)': '#fd8d3c',
    'Moderate (Possible Development)': '#fecc5c'
}
for pot_class, color in pot_colors.items():
    subset = grid[grid['potential_class'] == pot_class]
    if len(subset) > 0:
        subset.plot(ax=ax4, color=color, edgecolor='white', linewidth=0.3,
                   label=f'{pot_class} ({len(subset)})')

# Add city center
from shapely.geometry import Point
city_center = Point(7.6261, 51.9625)
city_center_proj = gpd.GeoSeries([city_center], crs="EPSG:4326").to_crs("EPSG:25832")[0]
ax4.scatter(city_center_proj.x, city_center_proj.y, c='blue', s=100, marker='*', 
            label='City Center', zorder=5)

ax4.legend(loc='lower right', fontsize=9)
ax4.set_title('Predicted Development Zones\n(Based on Historical Patterns & Spatial Analysis)', fontsize=12)
ax4.set_axis_off()

plt.suptitle('Münster Urban Expansion Analysis & Prediction', fontsize=14, fontweight='bold', y=0.98)
plt.tight_layout()
plt.savefig(output_dir / "growth_prediction_maps.png", dpi=150, bbox_inches='tight')
print(f"  Saved: {output_dir / 'growth_prediction_maps.png'}")

# ============================================================
# Additional: Direction-based prediction visualization
fig2, ax = plt.subplots(figsize=(14, 12))

# Show development potential with contours
grid.plot(ax=ax, column='dev_potential', cmap=cmap_pot, 
          legend=True, legend_kwds={'label': 'Development Potential', 'shrink': 0.5},
          edgecolor='none', alpha=0.8)

# Add direction arrows from city center
arrow_length = 3000  # meters
dir_angles = {'E': 0, 'NE': 45, 'N': 90, 'NW': 135, 'W': 180, 'SW': 225, 'S': 270, 'SE': 315}
dir_weights = grid.groupby('direction')['dev_potential'].mean().to_dict()

max_weight = max(dir_weights.values())
for d, angle in dir_angles.items():
    weight = dir_weights.get(d, 0) / max_weight
    if weight > 0.3:  # Only show significant directions
        rad = np.radians(angle)  # N=90° (up), E=0° (right), S=270° (down), W=180° (left)
        dx = arrow_length * weight * np.cos(rad)
        dy = arrow_length * weight * np.sin(rad)
        ax.annotate('', 
                   xy=(city_center_proj.x + dx, city_center_proj.y + dy),
                   xytext=(city_center_proj.x, city_center_proj.y),
                   arrowprops=dict(arrowstyle='->', color='darkblue', lw=2 + weight*3))
        ax.text(city_center_proj.x + dx*1.15, city_center_proj.y + dy*1.15, 
               f'{d}\n{weight*100:.0f}%', ha='center', va='center', fontsize=10, fontweight='bold')

ax.scatter(city_center_proj.x, city_center_proj.y, c='blue', s=200, marker='*', zorder=10)
ax.set_title('Predicted Growth Directions\n(Arrow size indicates development potential)', fontsize=14)
ax.set_axis_off()

plt.savefig(output_dir / "growth_direction_prediction.png", dpi=150, bbox_inches='tight')
print(f"  Saved: {output_dir / 'growth_direction_prediction.png'}")

# ============================================================
print("\n" + "=" * 60)
print("5. EXPORTING PREDICTION DATA")
print("=" * 60)

# Export high-potential areas for mapping
high_pot_export = grid[grid['dev_potential'] > 0.2].copy()
high_pot_export = high_pot_export.to_crs(epsg=4326)
export_cols = ['cell_id', 'direction', 'distance_km', 'dist_zone', 
               'total_new', 'recent_growth', 'dev_potential', 
               'potential_class', 'geometry']
high_pot_export[export_cols].to_file(output_dir / "predicted_growth_areas.geojson", driver='GeoJSON')
print(f"  Saved: {output_dir / 'predicted_growth_areas.geojson'}")

# Summary statistics
summary = {
    'total_grid_cells': len(grid),
    'high_potential_cells': int((grid['dev_potential'] > 0.4).sum()),
    'very_high_potential_cells': int((grid['dev_potential'] > 0.6).sum()),
    'predicted_growth_area_km2': float((grid['dev_potential'] > 0.4).sum() * 0.25),
    'top_growth_direction': high_pot_by_dir.index[0] if len(high_pot_by_dir) > 0 else 'N/A',
    'top_distance_zone': zone_potential['high_potential'].idxmax(),
    'avg_potential_score': float(grid['dev_potential'].mean())
}
pd.DataFrame([summary]).to_csv(output_dir / "prediction_summary.csv", index=False)
print(f"  Saved: {output_dir / 'prediction_summary.csv'}")

print("\n" + "=" * 60)
print("GROWTH PREDICTION COMPLETE")
print("=" * 60)
print(f"\n🎯 KEY PREDICTIONS:")
print(f"   • {summary['high_potential_cells']} grid cells have HIGH development potential")
print(f"   • Covering approximately {summary['predicted_growth_area_km2']:.1f} km²")
print(f"   • Primary growth direction: {summary['top_growth_direction']}")
print(f"   • Hottest distance zone: {summary['top_distance_zone']}")
