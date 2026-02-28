# Urban Expansion Analysis and Forecasting  
## Münster, Germany  

### Comprehensive Technical Report  

**Author:** Kazım Baran Yılmaz  
**Date:** February 2026  
**Course:** Spatio-Temporal Data Analysis  

[Interactive dashboard and report available online](https://kabarmaz.github.io/expboardmuenster/)

---

# Executive Summary

This report presents a comprehensive analysis of urban expansion in Münster, Germany, covering the period 2015 to 2025. Using OpenStreetMap building footprint data obtained through the ohsome API, the study investigates semiannual growth dynamics, spatial clustering patterns, directional trends, future development potential, and associated environmental impacts, including tree canopy loss and carbon sequestration effects.

## Key Findings

### Urban Growth Overview

| Indicator | Result |
|------------|--------|
| Building stock growth (2015 to 2025) | 105,422 to 135,576 |
| Absolute increase | +30,154 buildings |
| Relative growth | +28.6% |

### Spatial Dynamics

| Indicator | Result |
|------------|--------|
| Primary expansion direction | South and Southeast |
| Peak development zone | 6 to 10 km from city center |
| Global Moran's I | 0.25 |
| Statistical significance | p < 0.001 |

### Forecast (2025 to 2030)

| Indicator | Projection |
|------------|------------|
| Additional buildings | ~4,500 |
| Total buildings by 2030 | ~140,100 |
| Annual growth rate | ~900 buildings per year |

### Environmental Impact (2023 to 2030)

| Indicator | Estimated Impact |
|------------|------------------|
| Total canopy loss | 79.7 hectares |
| Trees affected | ~6,376 |
| Annual CO₂ sequestration loss | ~140 tonnes |

---

# 1. Introduction

## 1.1 Background

Urban expansion presents major challenges for sustainable planning. Understanding spatial growth patterns enables municipalities to:

- Anticipate infrastructure demand  
- Protect environmentally sensitive areas  
- Optimize land allocation  
- Assess ecological impacts  

Münster, a mid-sized German city with approximately 320,000 inhabitants, offers a suitable case study due to high-quality OpenStreetMap coverage and distinct suburban growth dynamics.

## 1.2 Objectives

1. Detect semiannual urban growth patterns using OSM building data  
2. Quantify spatial clustering and directional trends  
3. Forecast future development areas  
4. Estimate environmental impacts including canopy loss and CO₂ effects  
5. Provide interactive visualizations for decision support  

## 1.3 Study Area

| Attribute | Description |
|------------|-------------|
| City | Münster, North Rhine-Westphalia, Germany |
| Bounding box | 7.47°E to 7.77°E, 51.84°N to 52.06°N |
| Area | ~302 km² |
| Data CRS | WGS84 (EPSG:4326) |
| Analysis CRS | UTM 32N (EPSG:25832) |

---

# 2. Data and Methods

## 2.1 Data Acquisition

Building footprint data were retrieved from the ohsome API:

- Endpoint: `/elements/geometry`  
- Filter: `building=* and geometry:polygon`  
- Format: GeoJSON  
- Temporal resolution: Semiannual snapshots  

### Temporal Coverage

| Category | Snapshots | Period |
|----------|-----------|--------|
| Training data | 21 | 2015-01-01 to 2025-01-01 |
| Forecast horizon | 4 | 2025-07-01 to 2027-01-01 |

### Data Volume

- 21 GeoJSON snapshots  
- ~1.5 GB total size  
- 135,576 buildings as of 2025-01-01  

---

## 2.2 Spatial Aggregation

Buildings were aggregated into a regular grid:

| Parameter | Value |
|------------|-------|
| Grid size | 500 m × 500 m |
| Total cells | 2,484 |
| Active cells | 538 |
| Projection | EPSG:25832 |

---

## 2.3 Spatial Statistics

### Global Moran's I

$$
I = \frac{n}{\sum_i \sum_j w_{ij}} 
\cdot 
\frac{\sum_i \sum_j w_{ij}(x_i - \bar{x})(x_j - \bar{x})}
{\sum_i (x_i - \bar{x})^2}
$$

**Interpretation**

- \( I > 0 \): clustered  
- \( I = 0 \): random  
- \( I < 0 \): dispersed  

Overall Moran's I = 0.251 (p < 0.001).  
Urban development is moderately clustered and statistically significant.

---

### Local Indicators of Spatial Association (LISA)

| Cluster Type | Count | Share | Interpretation |
|--------------|-------|-------|---------------|
| Not significant | 1,498 | 60.3% | No pattern |
| Low-Low | 815 | 32.8% | Stable areas |
| High-High | 103 | 4.1% | Development hotspots |
| Low-High | 51 | 2.1% | Outliers |
| High-Low | 17 | 0.7% | Outliers |

High-High clusters are concentrated in the southern suburban ring.

---

## 2.4 Directional Analysis

### Growth Distribution by Direction

| Direction | Buildings | Share | Avg. Distance |
|------------|------------|--------|---------------|
| South | 936 | 23.9% | 5.8 km |
| Southeast | 889 | 22.7% | 6.2 km |
| Southwest | 656 | 16.8% | 5.4 km |
| Others combined | 1,429 | 36.6% | — |

63.4% of all new buildings were constructed in the southern semicircle.  
The weighted growth centroid shifted 6,576 meters toward the southwest.

---

## 2.5 Forecasting

Three models were combined:

1. Linear trend extrapolation  
2. Holt exponential smoothing  
3. Moving average  

Ensemble estimate:

$$
\hat{y}_{ensemble} = \frac{1}{3} (\hat{y}_{linear} + \hat{y}_{exp} + \hat{y}_{MA})
$$

### Five-Year Projection (2025 to 2030)

| Metric | Projection |
|------------|------------|
| New buildings | ~4,500 |
| Total buildings | ~140,100 |
| Growth rate | ~3.3% |

Peak development remains concentrated in southern sectors.

---

# 3. Environmental Impact

## 3.1 Canopy Loss Model

$$
C_{loss} = N_{buildings} \times A_{footprint} \times M_{dev} \times P_{canopy}(z)
$$

Assumptions:

- Average footprint: 150 m²  
- Development multiplier: 1.8  
- Zone-based canopy probabilities  

## 3.2 Total Estimated Impact (2023 to 2030)

| Impact Metric | Value | Equivalent |
|---------------|--------|------------|
| Total canopy loss | 79.7 ha | ~112 football fields |
| Trees affected | ~6,376 | — |
| Annual CO₂ loss | 140 tonnes | ~30 passenger cars |

The 6 to 10 km ring accounts for approximately 34% of total canopy loss.

---

# 4. Discussion

## 4.1 Spatial Patterns

Urban expansion follows a pronounced southward trajectory. Contributing factors likely include:

- Transportation accessibility  
- Availability of developable land  
- Regional economic connectivity  

The suburban ring effect indicates peak growth between 6 and 10 km from the city center.

## 4.2 Limitations

- OSM data quality variability  
- Model-based canopy estimation  
- Linear growth assumptions  
- Absence of socioeconomic variables  

---

# 5. Conclusions

1. Sustained urban growth of 28.6% over ten years  
2. Strong southward spatial concentration  
3. Statistically significant clustering (Moran's I = 0.25)  
4. Dominant suburban ring between 6 and 10 km  
5. Projected canopy loss approaching 80 hectares by 2030  
6. Forecastable spatial development patterns  

The methodology integrates spatial statistics, time series forecasting, and environmental modeling into a transferable framework for urban growth monitoring in OSM-covered regions.

---