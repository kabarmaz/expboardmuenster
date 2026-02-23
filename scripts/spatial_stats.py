"""
Spatial Statistics Analysis for Urban Expansion in Münster.

Performs:
1. Global Moran's I for spatial autocorrelation
2. Local Moran's I (LISA) for cluster detection
3. Getis-Ord Gi* for hotspot analysis
4. Growth directionality analysis
"""
import pandas as pd
import geopandas as gpd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.colors import TwoSlopeNorm
import os

from libpysal.weights import Queen, KNN
from esda.moran import Moran, Moran_Local
from esda.getisord import G_Local

# Output folder
OUT_DIR = 'output/spatial_stats'
os.makedirs(OUT_DIR, exist_ok=True)

# Load grid data
print("Loading grid data...")
grid = gpd.read_file('output/grid_new_buildings.geojson')

# Ensure projected CRS for spatial operations
if grid.crs.to_epsg() != 25832:
    grid = grid.to_crs('EPSG:25832')

# Get new building columns
new_cols = sorted([c for c in grid.columns if c.startswith('new_')])
print(f"Found {len(new_cols)} time periods")

# Calculate total new buildings across all available periods
grid['total_new'] = grid[new_cols].sum(axis=1)

# Create spatial weights matrix (Queen contiguity)
print("\nCreating spatial weights matrix...")
w = Queen.from_dataframe(grid, use_index=True)
w.transform = 'r'  # Row-standardize
print(f"  Neighbors: mean={w.mean_neighbors:.1f}, min={w.min_neighbors}, max={w.max_neighbors}")

# ============================================================
# 1. GLOBAL MORAN'S I
# ============================================================
print("\n" + "="*60)
print("1. GLOBAL MORAN'S I (Spatial Autocorrelation)")
print("="*60)

moran_results = []

for col in new_cols:
    y = grid[col].values
    if y.sum() == 0:
        continue
    
    moran = Moran(y, w)
    moran_results.append({
        'period': col.replace('new_', ''),
        'morans_i': moran.I,
        'expected_i': moran.EI,
        'z_score': moran.z_sim,
        'p_value': moran.p_sim,
        'significant': moran.p_sim < 0.05
    })
    
moran_df = pd.DataFrame(moran_results)
moran_df.to_csv(f'{OUT_DIR}/global_morans_i.csv', index=False)
print("\nGlobal Moran's I by period:")
print(moran_df.to_string(index=False))

# Moran's I for total new buildings
moran_total = Moran(grid['total_new'].values, w)
print(f"\nTotal New Buildings (all periods):")
print(f"  Moran's I: {moran_total.I:.4f}")
print(f"  Expected I: {moran_total.EI:.4f}")
print(f"  Z-score: {moran_total.z_sim:.2f}")
print(f"  p-value: {moran_total.p_sim:.4f}")
print(f"  Interpretation: {'Clustered' if moran_total.I > 0 else 'Dispersed'} pattern")

# Plot Moran's I over time
if len(moran_df) > 1:
    fig, ax = plt.subplots(figsize=(12, 5))
    periods = pd.to_datetime(moran_df['period'])
    ax.bar(periods, moran_df['morans_i'], alpha=0.7, color='steelblue')
    ax.axhline(y=0, color='red', linestyle='--', alpha=0.5)
    ax.set_xlabel('Period')
    ax.set_ylabel("Moran's I")
    ax.set_title("Global Moran's I Over Time (Spatial Clustering Strength)")
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig(f'{OUT_DIR}/morans_i_time_series.png', dpi=150)
    print(f"\n  Saved: {OUT_DIR}/morans_i_time_series.png")

# ============================================================
# 2. LOCAL MORAN'S I (LISA)
# ============================================================
print("\n" + "="*60)
print("2. LOCAL MORAN'S I (LISA Clusters)")
print("="*60)

# Compute LISA for total new buildings
lisa = Moran_Local(grid['total_new'].values, w)

# Classify clusters
# 1 = HH (hot spot), 2 = LH, 3 = LL (cold spot), 4 = HL
grid['lisa_cluster'] = lisa.q
grid['lisa_pvalue'] = lisa.p_sim
grid['lisa_significant'] = lisa.p_sim < 0.05

# Create cluster labels
cluster_labels = {1: 'High-High', 2: 'Low-High', 3: 'Low-Low', 4: 'High-Low', 0: 'Not Significant'}
grid['lisa_label'] = grid.apply(
    lambda row: cluster_labels[row['lisa_cluster']] if row['lisa_significant'] else 'Not Significant', 
    axis=1
)

# Count clusters
cluster_counts = grid['lisa_label'].value_counts()
print("\nLISA Cluster Distribution:")
for label, count in cluster_counts.items():
    print(f"  {label}: {count} cells")

# Save LISA results
lisa_cols = ['cell_id', 'total_new', 'lisa_cluster', 'lisa_pvalue', 'lisa_label', 'geometry']
grid[lisa_cols].to_file(f'{OUT_DIR}/lisa_clusters.geojson', driver='GeoJSON')
print(f"\n  Saved: {OUT_DIR}/lisa_clusters.geojson")

# Plot LISA map
fig, ax = plt.subplots(figsize=(12, 12))

colors = {
    'High-High': 'red',
    'Low-Low': 'blue', 
    'High-Low': 'orange',
    'Low-High': 'lightblue',
    'Not Significant': 'lightgray'
}

for label, color in colors.items():
    subset = grid[grid['lisa_label'] == label]
    if len(subset) > 0:
        subset.plot(ax=ax, color=color, edgecolor='white', linewidth=0.2, label=label)

ax.legend(loc='lower right', title='LISA Cluster')
ax.set_title('Local Moran\'s I Clusters - New Building Hotspots', fontsize=14)
ax.set_axis_off()
plt.tight_layout()
plt.savefig(f'{OUT_DIR}/lisa_cluster_map.png', dpi=150)
print(f"  Saved: {OUT_DIR}/lisa_cluster_map.png")

# ============================================================
# 3. GETIS-ORD Gi* HOTSPOT ANALYSIS
# ============================================================
print("\n" + "="*60)
print("3. GETIS-ORD Gi* HOTSPOT ANALYSIS")
print("="*60)

# Use KNN weights for Gi* (better for hotspot detection)
w_knn = KNN.from_dataframe(grid, k=8)

# Compute Gi* with fewer permutations for speed
g_local = G_Local(grid['total_new'].values, w_knn, star=True, permutations=99)

grid['gi_zscore'] = g_local.Zs
grid['gi_pvalue'] = g_local.p_sim

# Classify hotspots/coldspots
def classify_hotspot(row):
    if row['gi_pvalue'] > 0.05:
        return 'Not Significant'
    elif row['gi_zscore'] > 2.58:
        return 'Hot Spot (99%)'
    elif row['gi_zscore'] > 1.96:
        return 'Hot Spot (95%)'
    elif row['gi_zscore'] > 1.65:
        return 'Hot Spot (90%)'
    elif row['gi_zscore'] < -2.58:
        return 'Cold Spot (99%)'
    elif row['gi_zscore'] < -1.96:
        return 'Cold Spot (95%)'
    elif row['gi_zscore'] < -1.65:
        return 'Cold Spot (90%)'
    else:
        return 'Not Significant'

grid['hotspot_class'] = grid.apply(classify_hotspot, axis=1)

# Count hotspots
hotspot_counts = grid['hotspot_class'].value_counts()
print("\nGi* Hotspot Classification:")
for label, count in hotspot_counts.items():
    print(f"  {label}: {count} cells")

# Save hotspot results
hotspot_cols = ['cell_id', 'total_new', 'gi_zscore', 'gi_pvalue', 'hotspot_class', 'geometry']
grid[hotspot_cols].to_file(f'{OUT_DIR}/hotspots_gi.geojson', driver='GeoJSON')
print(f"\n  Saved: {OUT_DIR}/hotspots_gi.geojson")

# Plot Gi* z-scores
fig, ax = plt.subplots(figsize=(12, 12))

# Use diverging colormap centered at 0
norm = TwoSlopeNorm(vmin=grid['gi_zscore'].min(), vcenter=0, vmax=grid['gi_zscore'].max())
grid.plot(
    column='gi_zscore',
    cmap='RdBu_r',
    norm=norm,
    legend=True,
    legend_kwds={'label': 'Gi* Z-score', 'shrink': 0.6},
    ax=ax,
    edgecolor='white',
    linewidth=0.1
)
ax.set_title('Getis-Ord Gi* Hotspot Analysis - Urban Expansion', fontsize=14)
ax.set_axis_off()
plt.tight_layout()
plt.savefig(f'{OUT_DIR}/hotspot_gi_map.png', dpi=150)
print(f"  Saved: {OUT_DIR}/hotspot_gi_map.png")

# ============================================================
# 4. GROWTH DIRECTIONALITY ANALYSIS
# ============================================================
print("\n" + "="*60)
print("4. GROWTH DIRECTIONALITY ANALYSIS")
print("="*60)

# Get hotspot cells only (significant High-High or Hot Spot 95%+)
hotspots = grid[(grid['hotspot_class'].str.contains('Hot Spot')) | 
                (grid['lisa_label'] == 'High-High')]

if len(hotspots) > 0:
    # Calculate centroid of all hotspots
    hotspot_centroids = hotspots.geometry.centroid
    
    # Calculate center of city (center of all cells)
    city_center = grid.geometry.centroid.unary_union.centroid
    
    # Calculate mean centroid of hotspots
    hotspot_center = hotspot_centroids.unary_union.centroid
    
    # Direction vector from city center to hotspot center
    dx = hotspot_center.x - city_center.x
    dy = hotspot_center.y - city_center.y
    
    # Calculate angle (bearing)
    angle_rad = np.arctan2(dy, dx)
    angle_deg = np.degrees(angle_rad)
    
    # Convert to compass bearing (0 = North, 90 = East)
    compass_bearing = (90 - angle_deg) % 360
    
    # Determine cardinal direction
    directions = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW', 'N']
    dir_idx = int((compass_bearing + 22.5) // 45) % 8
    cardinal = directions[dir_idx]
    
    # Distance from center
    distance = np.sqrt(dx**2 + dy**2)
    
    print(f"\nGrowth Direction Analysis:")
    print(f"  City center: ({city_center.x:.0f}, {city_center.y:.0f})")
    print(f"  Hotspot center: ({hotspot_center.x:.0f}, {hotspot_center.y:.0f})")
    print(f"  Direction: {cardinal} ({compass_bearing:.1f}°)")
    print(f"  Distance from center: {distance:.0f} m")
    print(f"  Number of hotspot cells: {len(hotspots)}")
    
    # Save direction analysis
    direction_data = {
        'city_center_x': city_center.x,
        'city_center_y': city_center.y,
        'hotspot_center_x': hotspot_center.x,
        'hotspot_center_y': hotspot_center.y,
        'bearing_degrees': compass_bearing,
        'cardinal_direction': cardinal,
        'distance_m': distance,
        'hotspot_cell_count': len(hotspots)
    }
    pd.DataFrame([direction_data]).to_csv(f'{OUT_DIR}/growth_direction.csv', index=False)
    print(f"\n  Saved: {OUT_DIR}/growth_direction.csv")
    
    # Plot direction
    fig, ax = plt.subplots(figsize=(12, 12))
    
    # Plot all cells in gray
    grid.plot(ax=ax, color='lightgray', edgecolor='white', linewidth=0.1)
    
    # Plot hotspots in red
    hotspots.plot(ax=ax, color='red', edgecolor='darkred', linewidth=0.3, label='Growth Hotspots')
    
    # Plot direction arrow
    ax.annotate('', xy=(hotspot_center.x, hotspot_center.y), 
                xytext=(city_center.x, city_center.y),
                arrowprops=dict(arrowstyle='->', color='blue', lw=3))
    
    # Mark centers
    ax.plot(city_center.x, city_center.y, 'bo', markersize=15, label='City Center')
    ax.plot(hotspot_center.x, hotspot_center.y, 'r*', markersize=20, label='Growth Center')
    
    ax.set_title(f'Urban Growth Direction: {cardinal} ({compass_bearing:.0f}°)', fontsize=14)
    ax.legend(loc='lower right')
    ax.set_axis_off()
    plt.tight_layout()
    plt.savefig(f'{OUT_DIR}/growth_direction_map.png', dpi=150)
    print(f"  Saved: {OUT_DIR}/growth_direction_map.png")

else:
    print("  No significant hotspots found for direction analysis")

# ============================================================
# SUMMARY
# ============================================================
print("\n" + "="*60)
print("SPATIAL ANALYSIS SUMMARY")
print("="*60)

print(f"""
Key Findings:

1. Spatial Autocorrelation (Moran's I = {moran_total.I:.3f}):
   - {'Statistically significant' if moran_total.p_sim < 0.05 else 'Not significant'} clustering
   - New construction is {'spatially clustered' if moran_total.I > 0 else 'randomly distributed'}

2. LISA Clusters:
   - High-High (expansion hotspots): {cluster_counts.get('High-High', 0)} cells
   - Low-Low (stable areas): {cluster_counts.get('Low-Low', 0)} cells
   
3. Gi* Hotspots:
   - Hot Spots (99% conf): {hotspot_counts.get('Hot Spot (99%)', 0)} cells
   - Hot Spots (95% conf): {hotspot_counts.get('Hot Spot (95%)', 0)} cells

4. Growth Direction: {cardinal if len(hotspots) > 0 else 'N/A'}

Output files saved to: {OUT_DIR}/
""")

print("Done!")
