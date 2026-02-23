#!/usr/bin/env python3
"""
Growth Directionality Analysis
Analyzes the direction of urban expansion from city center
"""

import geopandas as gpd
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from shapely.geometry import Point
import os
from pathlib import Path

# Setup
output_dir = Path("output/spatial_stats")
output_dir.mkdir(parents=True, exist_ok=True)

print("Loading grid data...")
grid = gpd.read_file("output/grid_new_buildings.geojson")
grid = grid.to_crs(epsg=25832)

# City center of Münster (Dom/Prinzipalmarkt area)
CITY_CENTER = Point(7.6261, 51.9625)  # WGS84
city_center_proj = gpd.GeoSeries([CITY_CENTER], crs="EPSG:4326").to_crs("EPSG:25832")[0]

# Get grid centroids
grid['centroid'] = grid.geometry.centroid

# Calculate distance and angle from city center
def calculate_polar_coords(centroid):
    dx = centroid.x - city_center_proj.x
    dy = centroid.y - city_center_proj.y
    distance = np.sqrt(dx**2 + dy**2)
    angle = np.degrees(np.arctan2(dy, dx))  # -180 to 180
    if angle < 0:
        angle += 360  # Convert to 0-360
    return distance, angle

grid['distance_km'] = grid['centroid'].apply(lambda c: calculate_polar_coords(c)[0] / 1000)
grid['angle'] = grid['centroid'].apply(lambda c: calculate_polar_coords(c)[1])

# Assign cardinal/intercardinal directions
def get_direction(angle):
    dirs = ['E', 'NE', 'N', 'NW', 'W', 'SW', 'S', 'SE', 'E']
    idx = int((angle + 22.5) / 45) % 8
    return dirs[idx]

grid['direction'] = grid['angle'].apply(get_direction)

# Get period columns (columns starting with 'new_')
period_cols = [c for c in grid.columns if c.startswith('new_')]
period_cols = sorted(period_cols)

# Calculate total new buildings
grid['total_new'] = grid[period_cols].sum(axis=1)

print(f"\nFound {len(period_cols)} periods")
print("=" * 60)
print("GROWTH DIRECTIONALITY ANALYSIS")
print("=" * 60)

# 1. Growth by Direction (total)
print("\n1. Total New Buildings by Direction (2015-2025)")
direction_totals = grid.groupby('direction')['total_new'].sum()
direction_totals = direction_totals.sort_values(ascending=False)
print(direction_totals.to_string())

# 2. Growth by Distance Zone
print("\n2. New Buildings by Distance from Center")
grid['distance_zone'] = pd.cut(grid['distance_km'], 
                                bins=[0, 2, 4, 6, 8, 10, 15, 20],
                                labels=['0-2km', '2-4km', '4-6km', '6-8km', '8-10km', '10-15km', '15-20km'])
zone_totals = grid.groupby('distance_zone')['total_new'].sum()
print(zone_totals.to_string())

# 3. Temporal shift in growth direction
print("\n3. Growth Direction Over Time")
direction_time = []
for period in period_cols:
    period_dir = grid.groupby('direction')[period].sum()
    top_dir = period_dir.idxmax()
    # Extract date from column name (new_YYYY-MM-DD -> YYYY-MM-DD)
    period_date = period.replace('new_', '')
    direction_time.append({
        'period': period_date,
        'top_direction': top_dir,
        'buildings_in_top': period_dir[top_dir],
        'total_buildings': period_dir.sum()
    })

dir_df = pd.DataFrame(direction_time)
print(dir_df.to_string(index=False))
dir_df.to_csv(output_dir / "direction_over_time.csv", index=False)

# 4. Calculate growth centroid shift
print("\n4. Growth Centroid Shift")
centroids_over_time = []
for period in period_cols:
    weights = grid[period].values
    if weights.sum() > 0:
        cx = np.average(grid['centroid'].apply(lambda p: p.x), weights=weights)
        cy = np.average(grid['centroid'].apply(lambda p: p.y), weights=weights)
        centroids_over_time.append({
            'period': period,
            'centroid_x': cx,
            'centroid_y': cy,
            'dist_from_center_km': np.sqrt((cx - city_center_proj.x)**2 + (cy - city_center_proj.y)**2) / 1000
        })

centroid_df = pd.DataFrame(centroids_over_time)
print(centroid_df.to_string(index=False))

# Calculate shift from first to last
if len(centroid_df) >= 2:
    dx = centroid_df.iloc[-1]['centroid_x'] - centroid_df.iloc[0]['centroid_x']
    dy = centroid_df.iloc[-1]['centroid_y'] - centroid_df.iloc[0]['centroid_y']
    shift_dist = np.sqrt(dx**2 + dy**2)
    shift_angle = np.degrees(np.arctan2(dy, dx))
    if shift_angle < 0:
        shift_angle += 360
    shift_dir = get_direction(shift_angle)
    print(f"\nGrowth centroid shifted {shift_dist:.0f}m towards {shift_dir} ({shift_angle:.1f}°)")

# 5. Create polar plot of growth by direction
print("\n5. Creating visualizations...")

fig, axes = plt.subplots(1, 3, figsize=(18, 6))

# Plot 1: Polar bar chart - total growth by direction
ax1 = plt.subplot(131, projection='polar')
directions = ['E', 'NE', 'N', 'NW', 'W', 'SW', 'S', 'SE']
angles_rad = [np.radians(i * 45) for i in range(8)]
values = [direction_totals.get(d, 0) for d in directions]

# Polar bar needs to start from North and go clockwise
# Adjust: matplotlib polar starts at 3 o'clock (East) and goes counterclockwise
# We want to start at 12 o'clock (North) and go... let's just plot as-is for simplicity
bars = ax1.bar(angles_rad, values, width=0.6, alpha=0.7, color='steelblue', edgecolor='navy')
ax1.set_theta_zero_location('N')
ax1.set_theta_direction(-1)  # Clockwise
ax1.set_xticks(angles_rad)
ax1.set_xticklabels(['E', 'NE', 'N', 'NW', 'W', 'SW', 'S', 'SE'])
ax1.set_title('New Buildings by Direction\n(from city center)', pad=20)

# Plot 2: Distance zonation
ax2 = axes[1]
zone_totals.plot(kind='bar', ax=ax2, color='coral', edgecolor='darkred')
ax2.set_title('New Buildings by Distance from Center')
ax2.set_xlabel('Distance Zone')
ax2.set_ylabel('New Buildings')
ax2.tick_params(axis='x', rotation=45)

# Plot 3: Growth centroid path
ax3 = axes[2]
grid.plot(ax=ax3, column='total_new', cmap='YlOrRd', legend=True, alpha=0.7,
          legend_kwds={'label': 'New Buildings', 'shrink': 0.5})
ax3.scatter(city_center_proj.x, city_center_proj.y, c='blue', s=100, marker='*', 
            label='City Center', zorder=5)
if len(centroid_df) >= 2:
    ax3.plot(centroid_df['centroid_x'], centroid_df['centroid_y'], 
             'ko-', markersize=5, linewidth=2, label='Growth Centroid Path')
    ax3.scatter(centroid_df.iloc[0]['centroid_x'], centroid_df.iloc[0]['centroid_y'], 
                c='green', s=80, marker='s', label='2015 Centroid', zorder=6)
    ax3.scatter(centroid_df.iloc[-1]['centroid_x'], centroid_df.iloc[-1]['centroid_y'], 
                c='red', s=80, marker='s', label='2025 Centroid', zorder=6)
ax3.set_title('Growth Centroid Movement')
ax3.legend(loc='lower right')
ax3.set_axis_off()

plt.tight_layout()
plt.savefig(output_dir / "growth_directionality.png", dpi=150, bbox_inches='tight')
print(f"  Saved: {output_dir / 'growth_directionality.png'}")

# 6. Create map with direction sectors
fig, ax = plt.subplots(figsize=(12, 10))

# Color by direction
dir_colors = {
    'N': '#1f77b4', 'NE': '#ff7f0e', 'E': '#2ca02c', 'SE': '#d62728',
    'S': '#9467bd', 'SW': '#8c564b', 'W': '#e377c2', 'NW': '#7f7f7f'
}
grid['dir_color'] = grid['direction'].map(dir_colors)

# Only show cells with buildings
active = grid[grid['total_new'] > 0]
active.plot(ax=ax, color=active['dir_color'], alpha=0.7, edgecolor='white', linewidth=0.5)

# Add city center
ax.scatter(city_center_proj.x, city_center_proj.y, c='black', s=200, marker='*', 
           label='City Center', zorder=5)

# Legend
from matplotlib.patches import Patch
legend_elements = [Patch(facecolor=dir_colors[d], label=f'{d}: {direction_totals.get(d, 0):,.0f}') 
                   for d in directions if d in direction_totals.index]
ax.legend(handles=legend_elements, loc='lower right', title='New Buildings by Direction')

ax.set_title('Urban Expansion Direction\nMünster 2015-2025', fontsize=14)
ax.set_axis_off()
plt.savefig(output_dir / "direction_map.png", dpi=150, bbox_inches='tight')
print(f"  Saved: {output_dir / 'direction_map.png'}")

# Save direction analysis
grid_export = grid.drop(columns=['centroid'])
grid_export['direction'] = grid['direction']
grid_export['distance_km'] = grid['distance_km']
grid_export.to_file(output_dir / "grid_with_direction.geojson", driver='GeoJSON')
print(f"  Saved: {output_dir / 'grid_with_direction.geojson'}")

print("\n" + "=" * 60)
print("DIRECTIONALITY ANALYSIS COMPLETE")
print("=" * 60)
