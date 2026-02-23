# Urban Expansion Analysis and Forecasting: Münster, Germany
## Comprehensive Technical Report

**Author:** Kazım Baran Yılmaz  
**Date:** February 2026  
**Course:** Spatio-Temporal Data Analysis  

---

## Executive Summary

This report presents a comprehensive analysis of urban expansion patterns in Münster, Germany, spanning from 2015 to 2025. Using OpenStreetMap building footprint data obtained via the ohsome API, we analyzed semiannual growth patterns, identified spatial clusters of development, forecasted future expansion, and estimated environmental impacts including tree canopy loss.

### Key Findings

| Metric | Value |
|--------|-------|
| Building Stock Growth (2015-2025) | 105,422 → 135,576 (+28.6%) |
| Primary Expansion Direction | South/Southeast |
| Peak Development Zone | 6-10 km from city center |
| Moran's I (Spatial Clustering) | 0.25 (p < 0.001) |
| Projected Buildings (2025-2030) | ~4,500 additional |
| Estimated Canopy Loss (Total) | 79.7 hectares |
| CO2 Sequestration Impact | 140 tonnes/year |

---

## 1. Introduction

### 1.1 Background

Urban expansion is a critical concern for sustainable city planning. Understanding where and how cities grow enables planners to:
- Anticipate infrastructure needs
- Protect environmentally sensitive areas
- Optimize land use allocation
- Estimate environmental impacts

Münster, a mid-sized German city with approximately 320,000 inhabitants, serves as an ideal case study due to its well-documented OpenStreetMap coverage and characteristic suburban growth patterns.

### 1.2 Objectives

1. **Detect** semiannual urban growth patterns using OSM building data
2. **Analyze** spatial clustering and directional trends
3. **Forecast** future development areas
4. **Estimate** environmental impacts (tree canopy loss, CO2)
5. **Visualize** findings through interactive maps and dashboards

### 1.3 Study Area

- **City:** Münster, North Rhine-Westphalia, Germany
- **Bounding Box:** 7.47°E - 7.77°E, 51.84°N - 52.06°N
- **Area:** ~302 km²
- **Coordinate Systems:** 
  - WGS84 (EPSG:4326) for data acquisition
  - UTM 32N (EPSG:25832) for spatial analysis

---

## 2. Data and Methods

### 2.1 Data Acquisition

#### 2.1.1 Source: ohsome API

Building footprint data was obtained from the ohsome API (https://api.ohsome.org), which provides historical OpenStreetMap data through a RESTful interface.

**API Parameters:**
- **Endpoint:** `/elements/geometry`
- **Filter:** `building=* and geometry:polygon`
- **Format:** GeoJSON
- **Temporal Resolution:** Semiannual snapshots (6-month intervals)

**Request Configuration:**
```python
# Example API request structure
payload = {
    'bboxes': '7.47,51.84,7.77,52.06',
    'filter': 'building=* and geometry:polygon',
    'time': '2015-01-01',
    'properties': 'tags,metadata'
}
```

#### 2.1.2 Temporal Coverage

| Period | Snapshots | Date Range |
|--------|-----------|------------|
| Training Data | 21 | 2015-01-01 to 2025-01-01 |
| Forecast Period | 4 | 2025-07-01 to 2027-01-01 |

#### 2.1.3 Data Volume

- **Total Files:** 21 GeoJSON snapshots
- **Total Size:** ~1.5 GB
- **Final Building Count:** 135,576 (as of 2025-01-01)

### 2.2 Data Processing Pipeline

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  ohsome API     │────▶│  GeoJSON Files   │────▶│  Building IDs   │
│  (21 requests)  │     │  (1.5 GB total)  │     │  Extraction     │
└─────────────────┘     └──────────────────┘     └─────────────────┘
                                                          │
                                                          ▼
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  Grid-based     │◀────│  New Building    │◀────│  ID Comparison  │
│  Aggregation    │     │  Identification  │     │  (Set Diff)     │
└─────────────────┘     └──────────────────┘     └─────────────────┘
         │
         ▼
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  Spatial        │────▶│  Forecasting     │────▶│  Environmental  │
│  Statistics     │     │  Models          │     │  Impact         │
└─────────────────┘     └──────────────────┘     └─────────────────┘
```

#### 2.2.1 Building Identification

New buildings were identified through OSM ID tracking across temporal snapshots:

```python
# Pseudocode for new building detection
for each period t:
    current_ids = extract_building_ids(snapshot[t])
    previous_ids = extract_building_ids(snapshot[t-1])
    new_buildings[t] = current_ids - previous_ids
```

**Technical Implementation:**
- Used `ijson` for memory-efficient streaming of large GeoJSON files
- Parquet caching for faster subsequent loads
- Set operations for efficient ID comparison

#### 2.2.2 Spatial Aggregation

Buildings were aggregated into a regular grid for spatial analysis:

- **Grid Cell Size:** 500m × 500m
- **Total Cells:** 2,484
- **Active Cells (with growth):** 538
- **Projection:** EPSG:25832 (UTM 32N)

### 2.3 Spatial Analysis Methods

#### 2.3.1 Global Spatial Autocorrelation (Moran's I)

Moran's I statistic measures the degree of spatial clustering:

$$I = \frac{n}{\sum_i \sum_j w_{ij}} \cdot \frac{\sum_i \sum_j w_{ij}(x_i - \bar{x})(x_j - \bar{x})}{\sum_i (x_i - \bar{x})^2}$$

Where:
- $n$ = number of spatial units
- $w_{ij}$ = spatial weight between units $i$ and $j$
- $x_i$ = attribute value at location $i$
- $\bar{x}$ = mean attribute value

**Interpretation:**
- $I > 0$: Clustered pattern (similar values near each other)
- $I = 0$: Random pattern
- $I < 0$: Dispersed pattern

**Implementation:**
```python
from esda.moran import Moran
from libpysal.weights import Queen

w = Queen.from_dataframe(grid)
moran = Moran(grid['new_buildings'], w, permutations=999)
```

#### 2.3.2 Local Indicators of Spatial Association (LISA)

LISA identifies local clusters and spatial outliers:

$$I_i = \frac{(x_i - \bar{x})}{\sigma^2} \sum_j w_{ij}(x_j - \bar{x})$$

**Cluster Classifications:**
- **High-High (HH):** Hot spots - high values surrounded by high values
- **Low-Low (LL):** Cold spots - low values surrounded by low values
- **High-Low (HL):** Spatial outliers - high values surrounded by low
- **Low-High (LH):** Spatial outliers - low values surrounded by high

#### 2.3.3 Directional Analysis

Growth directionality was assessed relative to the city center (Dom/Prinzipalmarkt):

**City Center Coordinates:** 7.6261°E, 51.9625°N

```python
# Direction calculation
angle = arctan2(dy, dx)  # degrees from East
direction = classify_cardinal(angle)  # N, NE, E, SE, S, SW, W, NW
```

**Growth Centroid Tracking:**
Weighted centroid of new buildings calculated per period to track expansion trajectory.

### 2.4 Forecasting Methods

#### 2.4.1 Ensemble Approach

Three methods were combined for robust forecasting:

1. **Linear Trend Extrapolation**
   $$\hat{y}_{t+h} = \alpha + \beta \cdot (t+h)$$

2. **Exponential Smoothing (Holt's Method)**
   $$\hat{y}_{t+h} = l_t + h \cdot b_t$$
   Where $l_t$ is the level and $b_t$ is the trend component.

3. **Moving Average**
   $$\hat{y}_{t+h} = \frac{1}{k}\sum_{i=1}^{k} y_{t-i+1}$$

**Ensemble Forecast:**
$$\hat{y}_{ensemble} = \frac{1}{3}(\hat{y}_{linear} + \hat{y}_{exp} + \hat{y}_{MA})$$

#### 2.4.2 Development Potential Scoring

Spatial forecasting used a composite development potential score:

$$P_i = 0.35 \cdot R_i + 0.30 \cdot N_i + 0.20 \cdot T_i + 0.15 \cdot D_i$$

Where:
- $R_i$ = Normalized recent growth activity
- $N_i$ = Neighbor growth (spatial spillover)
- $T_i$ = Growth trend (acceleration)
- $D_i$ = Distance factor (suburban ring premium)

### 2.5 Environmental Impact Estimation

#### 2.5.1 Canopy Loss Model

Tree canopy loss was estimated based on development footprint:

$$C_{loss} = N_{buildings} \times A_{footprint} \times M_{dev} \times P_{canopy}(z)$$

Where:
- $N_{buildings}$ = Number of new buildings
- $A_{footprint}$ = Average building footprint (150 m²)
- $M_{dev}$ = Development multiplier (1.8x for roads, parking, etc.)
- $P_{canopy}(z)$ = Canopy coverage probability by zone

**Canopy Coverage by Distance Zone:**

| Zone | Distance | Canopy Coverage |
|------|----------|-----------------|
| Urban Core | 0-3 km | 15% |
| Inner Suburbs | 3-6 km | 25% |
| Outer Suburbs | 6-10 km | 35% |
| Peri-urban | 10-15 km | 45% |
| Rural Fringe | 15+ km | 55% |

#### 2.5.2 Carbon Impact

CO2 sequestration loss calculated using established urban forestry metrics:

$$CO_2 = T_{lost} \times 22 \text{ kg/tree/year}$$

Where 22 kg/tree/year is the average annual CO2 sequestration for mature urban trees.

---

## 3. Results

### 3.1 Building Growth Analysis

#### 3.1.1 Overall Trends

| Period | Total Buildings | New Buildings | Growth Rate |
|--------|-----------------|---------------|-------------|
| 2015-06-30 | 105,422 | (baseline) | - |
| 2017-01-01 | 127,599 | 22,177 | 21.0% |
| 2019-01-01 | 131,155 | 3,556 | 2.8% |
| 2021-01-01 | 132,584 | 1,429 | 1.1% |
| 2023-01-01 | 133,859 | 1,275 | 1.0% |
| 2025-01-01 | 135,576 | 1,717 | 1.3% |

**Observation:** High initial growth (2015-2017) reflects both actual construction and improved OSM mapping coverage. Recent years show stable growth of ~1-2% per period.

#### 3.1.2 Spatial Distribution

**Distance from City Center:**

| Zone | New Buildings | % of Total |
|------|---------------|------------|
| 0-3 km | 562 | 14.4% |
| 3-6 km | 1,181 | 30.2% |
| 6-10 km | 1,211 | 31.0% |
| 10-15 km | 872 | 22.3% |
| 15+ km | 84 | 2.1% |

**Finding:** Peak development occurs in the 3-10 km ring (61.2% of new buildings).

### 3.2 Spatial Statistics Results

#### 3.2.1 Global Moran's I

| Period | Moran's I | Z-score | p-value | Interpretation |
|--------|-----------|---------|---------|----------------|
| 2023-05-19 | 0.149 | 14.57 | 0.001 | Clustered |
| 2023-11-15 | 0.140 | 14.30 | 0.001 | Clustered |
| 2024-05-13 | 0.190 | 21.59 | 0.001 | Clustered |
| 2024-11-09 | 0.137 | 15.52 | 0.001 | Clustered |
| 2025-01-01 | 0.115 | 13.23 | 0.002 | Clustered |
| **Total** | **0.251** | **24.84** | **0.001** | **Clustered** |

**Interpretation:** All periods show statistically significant spatial clustering (p < 0.01). The overall Moran's I of 0.25 indicates moderate positive spatial autocorrelation — new buildings tend to cluster together rather than distribute randomly.

#### 3.2.2 LISA Clusters

| Cluster Type | Count | % | Interpretation |
|--------------|-------|---|----------------|
| Not Significant | 1,498 | 60.3% | No clear pattern |
| Low-Low | 815 | 32.8% | Cold spots (stable areas) |
| High-High | 103 | 4.1% | Hot spots (active development) |
| Low-High | 51 | 2.1% | Outliers |
| High-Low | 17 | 0.7% | Outliers |

**Finding:** 103 High-High clusters represent concentrated development hotspots, primarily located in the southern suburban ring.

### 3.3 Directional Analysis

#### 3.3.1 Growth by Direction

| Direction | New Buildings | % of Total | Avg. Distance |
|-----------|---------------|------------|---------------|
| **S (South)** | 936 | 23.9% | 5.8 km |
| **SE (Southeast)** | 889 | 22.7% | 6.2 km |
| **SW (Southwest)** | 656 | 16.8% | 5.4 km |
| E (East) | 364 | 9.3% | 7.1 km |
| NE (Northeast) | 321 | 8.2% | 6.8 km |
| NW (Northwest) | 297 | 7.6% | 5.9 km |
| W (West) | 251 | 6.4% | 5.1 km |
| N (North) | 196 | 5.0% | 4.9 km |

**Finding:** **63.4% of new development** occurred in the southern semicircle (S, SE, SW), indicating a clear southward expansion trend.

#### 3.3.2 Growth Centroid Migration

The weighted centroid of new buildings shifted over time:

- **Total Shift:** 6,576 meters
- **Direction:** Southwest (225.3°)
- **Interpretation:** Urban expansion is moving outward and southward

### 3.4 Forecasting Results

#### 3.4.1 Time Series Forecast (2025-2027)

| Period | Linear | Exp. Smooth | Simple Avg | Ensemble |
|--------|--------|-------------|------------|----------|
| 2025-07 | 647 | 210 | 660 | **506** |
| 2026-01 | 629 | 71 | 660 | **453** |
| 2026-07 | 610 | 0 | 660 | **424** |
| 2027-01 | 592 | 0 | 660 | **417** |

**Annual Forecast:** ~900 new buildings per year (2025-2027)

#### 3.4.2 5-Year Projection (2025-2030)

| Metric | Projection |
|--------|------------|
| New Buildings | ~4,500 |
| Total Buildings (2030) | ~140,100 |
| Growth Rate | 3.3% |

#### 3.4.3 Spatial Forecast

**Development Potential Classification:**

| Category | Cells | Area (km²) |
|----------|-------|------------|
| Very High | 104 | 26.0 |
| High | 171 | 42.8 |
| Moderate | 320 | 80.0 |
| Low | 1,889 | 472.3 |

**Predicted Hottest Zones:**
1. South (S): 68 high-potential cells
2. Southeast (SE): 67 high-potential cells
3. Southwest (SW): 38 high-potential cells

### 3.5 Environmental Impact

#### 3.5.1 Historical Canopy Loss (2023-2025)

| Period | Buildings | Canopy Loss (ha) | Trees Lost | CO2 Impact (t/yr) |
|--------|-----------|------------------|------------|-------------------|
| 2023-05 | 1,395 | 13.18 | 1,055 | 23.2 |
| 2023-11 | 763 | 7.21 | 577 | 12.7 |
| 2024-05 | 727 | 6.87 | 550 | 12.1 |
| 2024-11 | 692 | 6.54 | 523 | 11.5 |
| 2025-01 | 333 | 3.15 | 252 | 5.5 |
| **Total** | **3,910** | **33.5** | **2,683** | **59.0** |

#### 3.5.2 Projected Canopy Loss (2025-2030)

| Metric | Projection |
|--------|------------|
| Canopy at Risk | 46.2 hectares |
| Trees at Risk | ~3,693 |
| CO2 Sequestration Lost | 81.2 tonnes/year |

#### 3.5.3 Total Environmental Cost

| Impact Area | Value | Equivalent |
|-------------|-------|------------|
| Total Canopy | 79.7 ha | 112 football fields |
| Total Trees | ~6,376 | - |
| Annual CO2 Loss | 140 t/year | 30 cars removed |

#### 3.5.4 Canopy Loss by Zone

| Distance Zone | Canopy Loss (ha) | Trees Lost |
|---------------|------------------|------------|
| 0-3 km | 2.28 | 182 |
| 3-6 km | 7.97 | 638 |
| **6-10 km** | **11.44** | **916** |
| 10-15 km | 10.59 | 848 |
| 15+ km | 1.25 | 100 |

**Finding:** The 6-10 km zone experiences the highest canopy impact (34% of total loss).

---

## 4. Discussion

### 4.1 Interpretation of Findings

#### 4.1.1 Spatial Patterns

The analysis reveals a clear **southward suburban expansion** pattern in Münster. This aligns with:
- Transportation corridor development (A1 highway to the south)
- Available developable land
- Economic connections to the Ruhr metropolitan area

The Moran's I value of 0.25 confirms that development is **spatially clustered** rather than random, suggesting planned subdivision developments and organic neighborhood growth patterns.

#### 4.1.2 Development Dynamics

The "suburban ring effect" (peak growth at 6-10 km) reflects:
- Land availability constraints in the urban core
- Affordability considerations
- Family housing preferences
- Infrastructure availability

#### 4.1.3 Environmental Implications

The estimated canopy loss of 80 hectares by 2030 represents a significant environmental cost. However, it should be noted that:
- New developments may include compensatory tree planting
- Urban trees in new developments can partially offset losses
- Building density affects per-unit environmental impact

### 4.2 Limitations

1. **Data Source Limitations**
   - OSM data quality varies spatially
   - Volunteer mapping introduces temporal bias
   - Building demolitions may not be consistently recorded

2. **Methodological Limitations**
   - Canopy estimates are model-based, not remotely sensed
   - Linear extrapolation assumes consistent growth patterns
   - 500m grid may mask fine-grained patterns

3. **Forecast Uncertainty**
   - Economic factors not incorporated
   - Planning policy changes not modeled
   - Climate impacts on construction not considered

### 4.3 Recommendations

#### For Urban Planners:
1. **Focus green infrastructure investments** in the southern growth corridor
2. **Implement tree preservation ordinances** in the 6-10 km zone
3. **Monitor High-High LISA clusters** for infrastructure pressure

#### For Environmental Management:
1. **Establish canopy targets** for new developments (e.g., 20% minimum)
2. **Create green corridors** connecting suburban developments
3. **Prioritize urban forest management** in stable (Low-Low) areas

#### For Future Research:
1. Integrate satellite imagery for canopy validation
2. Include socioeconomic variables in forecasting
3. Model transportation impacts of expansion patterns

---

## 5. Technical Implementation

### 5.1 Software Environment

| Component | Version/Details |
|-----------|-----------------|
| Python | 3.10 |
| GeoPandas | 0.14.x |
| Pandas | 2.x |
| NumPy | 1.x |
| Matplotlib | 3.x |
| Folium | 0.14.x |
| libpysal | 4.x |
| esda | 2.x |
| statsmodels | 0.14.x |

### 5.2 File Structure

```
PROJECT/
├── scripts/
│   ├── ohsome_fetch.py         # Data acquisition
│   ├── analysis_lite.py        # Building tracking
│   ├── visualize.py            # EDA visualizations
│   ├── spatial_stats.py        # Moran's I, LISA
│   ├── directionality.py       # Growth direction analysis
│   ├── forecasting.py          # Time series forecasting
│   ├── growth_prediction.py    # Spatial forecasting
│   ├── canopy_analysis.py      # Environmental impact
│   ├── interactive_map.py      # Folium maps
│   └── prediction_map.py       # Interactive forecast map
├── data/
│   └── buildings/              # GeoJSON snapshots (21 files)
├── output/
│   ├── figures/                # Static visualizations
│   ├── spatial_stats/          # Moran's I, LISA outputs
│   ├── forecasting/            # Forecast results
│   ├── growth_prediction/      # Spatial predictions
│   ├── canopy_analysis/        # Environmental impact
│   └── interactive/            # HTML maps
└── requests/                   # API request logs
```

### 5.3 Reproducibility

All analyses can be reproduced by running:
```bash
# 1. Fetch data (requires internet)
python scripts/ohsome_fetch.py --start 2015-01-01 --end 2025-01-01

# 2. Process and analyze
python scripts/analysis_lite.py
python scripts/visualize.py
python scripts/spatial_stats.py
python scripts/directionality.py
python scripts/forecasting.py
python scripts/growth_prediction.py
python scripts/canopy_analysis.py
python scripts/interactive_map.py
python scripts/prediction_map.py
python scripts/canopy_map.py
```

---

## 6. Conclusions

This comprehensive analysis of urban expansion in Münster reveals:

1. **Consistent Growth:** The city added ~30,000 buildings (28.6%) over 10 years
2. **Southward Expansion:** 63% of new development in the southern semicircle
3. **Spatial Clustering:** Moran's I = 0.25 confirms non-random development patterns
4. **Suburban Ring Effect:** Peak development at 6-10 km from center
5. **Environmental Cost:** Projected 80 hectares of canopy loss by 2030
6. **Predictable Patterns:** Development potential scoring identifies future hotspots

The methodologies and tools developed in this project provide a replicable framework for urban expansion monitoring in any region with OSM coverage. The integration of spatial statistics with time-series forecasting and environmental impact assessment offers a holistic view of urbanization dynamics.

---

## References

1. ohsome API Documentation. (2024). Heidelberg Institute for Geoinformation Technology. https://docs.ohsome.org/
2. Rey, S. J., & Anselin, L. (2010). PySAL: A Python library of spatial analytical methods. In Handbook of applied spatial analysis (pp. 175-193). Springer.
3. Anselin, L. (1995). Local indicators of spatial association—LISA. Geographical Analysis, 27(2), 93-115.
4. Nowak, D. J., & Crane, D. E. (2002). Carbon storage and sequestration by urban trees in the USA. Environmental Pollution, 116(3), 381-389.
5. OpenStreetMap contributors. (2024). OpenStreetMap. https://www.openstreetmap.org/

---

## Appendix A: Output Files

### A.1 Data Files
- `building_growth_summary.csv` - Period-by-period building counts
- `grid_new_buildings.geojson` - 500m aggregation grid
- `lisa_clusters.geojson` - LISA cluster classifications
- `predicted_growth_areas.geojson` - Development potential zones
- `canopy_loss_map.geojson` - Environmental impact spatial data

### A.2 Visualizations
- `time_series_new_buildings.png` - Building growth time series
- `hotspot_map.png` - Spatial distribution of new buildings
- `lisa_cluster_map.png` - LISA cluster visualization
- `growth_prediction_maps.png` - Multi-panel prediction dashboard
- `canopy_loss_analysis.png` - Environmental impact dashboard

### A.3 Interactive Maps
- `overview_map.html` - Total growth overview
- `time_slider_map.html` - Temporal animation
- `direction_map.html` - Growth by direction
- `prediction_map.html` - Future development zones
- `canopy_loss_map.html` - Environmental impact map

---

*End of Report*
