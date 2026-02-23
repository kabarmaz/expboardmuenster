#!/usr/bin/env python3
"""
Urban Growth Time-Series Forecasting
SARIMAX and trend analysis for Münster building expansion
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
import warnings
warnings.filterwarnings('ignore')

# Setup
output_dir = Path("output/forecasting")
output_dir.mkdir(parents=True, exist_ok=True)

print("Loading building growth data...")
df = pd.read_csv("output/building_growth_summary.csv")
print(f"Loaded {len(df)} periods")
print(df.head())

# Parse dates - column is 'period_end'
df['end_date'] = pd.to_datetime(df['period_end'])
df = df.sort_values('end_date').reset_index(drop=True)

# Calculate growth percentage
df['growth_pct'] = df['new_buildings'] / df['total_buildings'].shift(1) * 100
df['growth_pct'] = df['growth_pct'].fillna(0)

# Create time series
# First period (index 0) is baseline - all existing buildings, not growth
# Skip it for trend analysis
ts = df.set_index('end_date')[['new_buildings', 'total_buildings', 'growth_pct']]
ts = ts[ts.index > '2015-07-01']  # Skip first period (baseline)

print(f"\nTime series from {ts.index.min()} to {ts.index.max()}")
print(f"Total new buildings: {ts['new_buildings'].sum():,}")
print(f"Mean per period: {ts['new_buildings'].mean():.1f}")
print(f"Std dev: {ts['new_buildings'].std():.1f}")

# ============================================================
print("\n" + "=" * 60)
print("1. TREND ANALYSIS")
print("=" * 60)

# Calculate rolling averages
ts['rolling_mean_4'] = ts['new_buildings'].rolling(window=4, min_periods=2).mean()

# Linear trend
from scipy import stats
x = np.arange(len(ts))
slope, intercept, r_value, p_value, std_err = stats.linregress(x, ts['new_buildings'])
ts['trend'] = intercept + slope * x

print(f"\nLinear Trend:")
print(f"  Slope: {slope:.2f} buildings/period")
print(f"  R²: {r_value**2:.3f}")
print(f"  p-value: {p_value:.4f}")

# Trend interpretation
if slope > 0:
    trend_dir = "increasing"
else:
    trend_dir = "decreasing"
print(f"  Interpretation: {trend_dir} trend")

# ============================================================
print("\n" + "=" * 60)
print("2. SIMPLE FORECASTING")
print("=" * 60)

# Forecast next 4 periods (2 years)
n_forecast = 4
last_idx = len(ts)
future_idx = np.arange(last_idx, last_idx + n_forecast)

# Use only last 8 periods (~4 years) for more relevant forecasting
recent_ts = ts.tail(8)
x_recent = np.arange(len(recent_ts))
slope_recent, intercept_recent, r_recent, p_recent, _ = stats.linregress(x_recent, recent_ts['new_buildings'])

print(f"\nRecent trend (last 4 years):")
print(f"  Slope: {slope_recent:.2f} buildings/period")
print(f"  R²: {r_recent**2:.3f}")

# Method 1: Linear extrapolation (recent trend)
forecast_linear = np.maximum(0, intercept_recent + slope_recent * (np.arange(len(recent_ts), len(recent_ts) + n_forecast)))

# Method 2: Exponential smoothing
from statsmodels.tsa.holtwinters import ExponentialSmoothing
try:
    model_es = ExponentialSmoothing(
        ts['new_buildings'].values, 
        trend='add',
        seasonal=None,  # Not enough data for seasonal
        damped_trend=True
    )
    fit_es = model_es.fit(optimized=True)
    forecast_es = np.maximum(0, fit_es.forecast(n_forecast))
except Exception as e:
    print(f"  Exponential smoothing failed: {e}")
    forecast_es = forecast_linear  # Fallback

# Method 3: Simple average of last 4 periods
forecast_simple = np.full(n_forecast, ts['new_buildings'].tail(4).mean())

# Generate forecast dates
last_date = ts.index[-1]
forecast_dates = pd.date_range(start=last_date, periods=n_forecast+1, freq='6MS')[1:]

# Create forecast dataframe
forecast_df = pd.DataFrame({
    'date': forecast_dates,
    'linear': forecast_linear,
    'exp_smooth': forecast_es,
    'simple_avg': forecast_simple
})
# Ensemble with floor at 0
forecast_df['ensemble'] = np.maximum(0, (forecast_df['linear'] + forecast_df['exp_smooth'] + forecast_df['simple_avg']) / 3)

print("\nForecasts for next 2 years (4 periods):")
print(forecast_df.to_string(index=False))

# Annual forecast
annual_forecast = forecast_df['ensemble'].sum() / 2  # 4 periods = 2 years
print(f"\nPredicted annual new buildings: ~{annual_forecast:.0f}")

# Export forecasts
forecast_df.to_csv(output_dir / "forecasts.csv", index=False)
print(f"\nSaved: {output_dir / 'forecasts.csv'}")

# ============================================================
print("\n" + "=" * 60)
print("3. VISUALIZATIONS")
print("=" * 60)

# Plot 1: Time series with forecasts
fig, axes = plt.subplots(2, 2, figsize=(14, 10))

# Main time series with forecasts
ax1 = axes[0, 0]
ax1.plot(ts.index, ts['new_buildings'], 'b-o', label='Observed', markersize=6)
ax1.plot(ts.index, ts['trend'], 'r--', label=f'Linear Trend (R²={r_value**2:.2f})', alpha=0.7)
ax1.plot(ts.index, ts['rolling_mean_4'], 'g-', label='4-period Rolling Mean', alpha=0.7)
ax1.plot(forecast_dates, forecast_df['ensemble'], 'mo--', label='Ensemble Forecast', markersize=8)
ax1.fill_between(forecast_dates, 
                  forecast_df['ensemble'] * 0.8, 
                  forecast_df['ensemble'] * 1.2,
                  color='magenta', alpha=0.2, label='±20% Confidence')
ax1.axvline(ts.index[-1], color='gray', linestyle=':', alpha=0.5)
ax1.set_title('Building Growth Forecast')
ax1.set_xlabel('Date')
ax1.set_ylabel('New Buildings per Period')
ax1.legend(loc='upper right')
ax1.grid(True, alpha=0.3)

# Cumulative growth with projection
ax2 = axes[0, 1]
cumulative = ts['new_buildings'].cumsum()
ax2.plot(ts.index, cumulative, 'b-o', label='Observed Cumulative', markersize=6)
cumulative_forecast = cumulative.iloc[-1] + forecast_df['ensemble'].cumsum().values
ax2.plot(forecast_dates, cumulative_forecast, 'mo--', label='Projected', markersize=8)
ax2.set_title('Cumulative New Buildings')
ax2.set_xlabel('Date')
ax2.set_ylabel('Total New Buildings')
ax2.legend()
ax2.grid(True, alpha=0.3)

# YoY growth rate
ax3 = axes[1, 0]
annual_growth = df.groupby(df['end_date'].dt.year)['new_buildings'].sum()
ax3.bar(annual_growth.index, annual_growth.values, color='steelblue', edgecolor='navy')
ax3.set_title('Annual New Buildings')
ax3.set_xlabel('Year')
ax3.set_ylabel('New Buildings')
ax3.grid(True, alpha=0.3, axis='y')

# Seasonality check (half-year patterns)
ax4 = axes[1, 1]
ts['half'] = ts.index.month.map(lambda m: 'First Half (Jan-Jun)' if m <= 6 else 'Second Half (Jul-Dec)')
half_year = ts.groupby('half')['new_buildings'].mean()
ax4.bar(half_year.index, half_year.values, color=['coral', 'lightblue'])
ax4.set_title('Seasonal Pattern (Half-Year)')
ax4.set_ylabel('Mean New Buildings')
ax4.grid(True, alpha=0.3, axis='y')

plt.tight_layout()
plt.savefig(output_dir / "forecast_analysis.png", dpi=150, bbox_inches='tight')
print(f"Saved: {output_dir / 'forecast_analysis.png'}")

# ============================================================
print("\n" + "=" * 60)
print("4. GROWTH PROJECTIONS")
print("=" * 60)

# Project total buildings
current_total = df['total_buildings'].iloc[-1]
print(f"\nCurrent total buildings (2025): {current_total:,}")

# Linear projection for 2030
periods_to_2030 = 10  # 5 years * 2 periods
projected_new_2030 = forecast_df['ensemble'].mean() * periods_to_2030
projected_total_2030 = current_total + projected_new_2030

print(f"Projected new buildings 2025-2030: ~{projected_new_2030:,.0f}")
print(f"Projected total buildings (2030): ~{projected_total_2030:,.0f}")
print(f"Growth rate 2025-2030: ~{100*projected_new_2030/current_total:.1f}%")

# Estimate area impact
AVG_BUILDING_AREA_SQM = 150  # Approximate average building footprint
projected_area_ha = projected_new_2030 * AVG_BUILDING_AREA_SQM / 10000
print(f"\nEstimated new building footprint area:")
print(f"  2025-2030: ~{projected_area_ha:.1f} hectares")
print(f"  (assuming avg {AVG_BUILDING_AREA_SQM}m² per building)")

# Save summary
summary = {
    'current_total_buildings': current_total,
    'forecast_period': '2025-2027',
    'forecast_new_buildings_per_period': forecast_df['ensemble'].mean(),
    'projected_total_2030': projected_total_2030,
    'linear_trend_slope': slope,
    'linear_trend_r2': r_value**2,
    'avg_building_area_sqm': AVG_BUILDING_AREA_SQM,
    'projected_area_ha_2030': projected_area_ha
}
pd.DataFrame([summary]).to_csv(output_dir / "forecast_summary.csv", index=False)
print(f"\nSaved: {output_dir / 'forecast_summary.csv'}")

print("\n" + "=" * 60)
print("FORECASTING COMPLETE")
print("=" * 60)
