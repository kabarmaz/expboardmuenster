"""
EDA Visualizations for Urban Expansion in Münster.

Creates:
1. Time series of new buildings per period
2. Map of new building density
3. Summary statistics
"""
import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np
from datetime import datetime
import os

# Output folder
OUT_DIR = 'output/figures'
os.makedirs(OUT_DIR, exist_ok=True)

# Load data
print("Loading data...")
summary = pd.read_csv('output/building_growth_summary.csv')
summary['period_end'] = pd.to_datetime(summary['period_end'])
grid = gpd.read_file('output/grid_new_buildings.geojson')

# 1. Time Series Plot
print("Creating time series plot...")
fig, ax = plt.subplots(figsize=(12, 6))

# Plot new buildings (excluding first period which is baseline)
x = summary['period_end'].iloc[1:]
y = summary['new_buildings'].iloc[1:]

ax.bar(x, y, width=150, color='steelblue', alpha=0.7, edgecolor='navy')
ax.plot(x, y, 'o-', color='navy', markersize=6)

ax.set_xlabel('Date', fontsize=12)
ax.set_ylabel('New Buildings', fontsize=12)
ax.set_title('Semiannual New Building Construction in Münster (2015-2025)', fontsize=14)
ax.xaxis.set_major_locator(mdates.YearLocator())
ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y'))
plt.xticks(rotation=45)
ax.grid(axis='y', alpha=0.3)

# Add trend line
z = np.polyfit(range(len(y)), y.values, 1)
p = np.poly1d(z)
ax.plot(x, p(range(len(y))), '--', color='red', alpha=0.7, label=f'Trend')
ax.legend()

plt.tight_layout()
plt.savefig(f'{OUT_DIR}/time_series_new_buildings.png', dpi=150)
print(f"  Saved: {OUT_DIR}/time_series_new_buildings.png")

# 2. Cumulative Growth Plot
print("Creating cumulative growth plot...")
fig, ax = plt.subplots(figsize=(12, 6))

ax.fill_between(summary['period_end'], summary['total_buildings'], alpha=0.3, color='steelblue')
ax.plot(summary['period_end'], summary['total_buildings'], '-o', color='navy', markersize=5)

ax.set_xlabel('Date', fontsize=12)
ax.set_ylabel('Total Buildings', fontsize=12)
ax.set_title('Total Building Stock in Münster (2015-2025)', fontsize=14)
ax.xaxis.set_major_locator(mdates.YearLocator())
ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y'))
plt.xticks(rotation=45)
ax.grid(alpha=0.3)

# Add annotations
start = summary.iloc[0]['total_buildings']
end = summary.iloc[-1]['total_buildings']
growth_pct = (end - start) / start * 100
ax.annotate(f'{start:,}', (summary.iloc[0]['period_end'], start), 
            textcoords="offset points", xytext=(0,10), ha='center')
ax.annotate(f'{end:,}\n(+{growth_pct:.1f}%)', (summary.iloc[-1]['period_end'], end), 
            textcoords="offset points", xytext=(0,10), ha='center')

plt.tight_layout()
plt.savefig(f'{OUT_DIR}/cumulative_growth.png', dpi=150)
print(f"  Saved: {OUT_DIR}/cumulative_growth.png")

# 3. Hotspot Map (recent periods)
print("Creating hotspot map...")

# Sum new buildings across recent periods
new_cols = [c for c in grid.columns if c.startswith('new_')]
grid['total_recent_new'] = grid[new_cols].sum(axis=1)

fig, ax = plt.subplots(figsize=(12, 12))
grid.to_crs('EPSG:25832').plot(
    column='total_recent_new',
    cmap='YlOrRd',
    scheme='quantiles',
    k=7,
    legend=True,
    legend_kwds={'title': 'New Buildings\n(2022-2025)', 'loc': 'lower right'},
    ax=ax,
    edgecolor='lightgray',
    linewidth=0.1
)
ax.set_title('Urban Expansion Hotspots in Münster (Recent 2022-2025)', fontsize=14)
ax.set_axis_off()

plt.tight_layout()
plt.savefig(f'{OUT_DIR}/hotspot_map.png', dpi=150)
print(f"  Saved: {OUT_DIR}/hotspot_map.png")

# 4. Bar chart by year
print("Creating annual summary...")
summary['year'] = summary['period_end'].dt.year

# Skip first period (baseline)
annual = summary.iloc[1:].groupby('year')['new_buildings'].sum().reset_index()

fig, ax = plt.subplots(figsize=(10, 6))
bars = ax.bar(annual['year'], annual['new_buildings'], color='steelblue', edgecolor='navy')
ax.set_xlabel('Year', fontsize=12)
ax.set_ylabel('New Buildings', fontsize=12)
ax.set_title('Annual New Building Construction in Münster', fontsize=14)
ax.grid(axis='y', alpha=0.3)

# Add value labels
for bar, val in zip(bars, annual['new_buildings']):
    ax.annotate(f'{int(val):,}', 
                xy=(bar.get_x() + bar.get_width()/2, bar.get_height()),
                xytext=(0, 3), textcoords='offset points',
                ha='center', va='bottom', fontsize=9)

plt.tight_layout()
plt.savefig(f'{OUT_DIR}/annual_new_buildings.png', dpi=150)
print(f"  Saved: {OUT_DIR}/annual_new_buildings.png")

# 5. Print summary stats
print("\n" + "="*60)
print("Urban Expansion Summary Statistics (2015-2025)")
print("="*60)
print(f"\nBuilding Stock:")
print(f"  Initial (2015): {summary.iloc[0]['total_buildings']:,}")
print(f"  Final (2025): {summary.iloc[-1]['total_buildings']:,}")
print(f"  Net Growth: {summary.iloc[-1]['total_buildings'] - summary.iloc[0]['total_buildings']:,}")
print(f"  % Growth: {(summary.iloc[-1]['total_buildings'] - summary.iloc[0]['total_buildings']) / summary.iloc[0]['total_buildings'] * 100:.1f}%")

print(f"\nNew Construction:")
print(f"  Total New (excluding baseline): {summary.iloc[1:]['new_buildings'].sum():,}")
print(f"  Average per period: {summary.iloc[1:]['new_buildings'].mean():.0f}")
print(f"  Peak period: {summary.iloc[1:].loc[summary.iloc[1:]['new_buildings'].idxmax(), 'period_end'].strftime('%Y-%m-%d')} ({summary.iloc[1:]['new_buildings'].max():,} buildings)")

# Find trend
new_vals = summary.iloc[1:]['new_buildings'].values
first_half = new_vals[:len(new_vals)//2].mean()
second_half = new_vals[len(new_vals)//2:].mean()
trend = "increasing" if second_half > first_half else "decreasing"
print(f"\nTrend Analysis:")
print(f"  First half average: {first_half:.0f} buildings/period")
print(f"  Second half average: {second_half:.0f} buildings/period")
print(f"  Overall trend: {trend}")

print("\nDone! Figures saved to:", OUT_DIR)
