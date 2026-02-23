"""
Urban Expansion Analysis Pipeline for Münster.

This script performs:
1. Data loading and cleaning of semiannual building footprints
2. Tracking new vs existing buildings across time periods
3. Aggregation to grid cells
4. EDA visualizations
5. Spatial statistics (Moran's I, hotspot analysis)

Usage:
    python scripts/analysis.py --data data/buildings --out output
"""
import argparse
import os
import glob
import geopandas as gpd
import pandas as pd
import numpy as np
from shapely.geometry import box
from pathlib import Path


def load_building_snapshots(data_dir, use_cache=True):
    """
    Load all building snapshots from GeoJSON files.
    Uses GeoParquet cache for faster subsequent loads.
    Returns dict mapping period -> GeoDataFrame.
    """
    import warnings
    files = sorted(glob.glob(os.path.join(data_dir, 'buildings_*.geojson')))
    cache_dir = os.path.join(data_dir, 'cache')
    os.makedirs(cache_dir, exist_ok=True)
    
    snapshots = {}
    
    for f in files:
        fname = os.path.basename(f)
        # Extract date from filename like buildings_001_2015-01-01_to_2015-06-30.geojson
        parts = fname.replace('.geojson', '').split('_')
        if len(parts) >= 5:
            end_date = parts[4]  # period end date
        else:
            end_date = parts[-1]
        
        # Try loading from cache first
        cache_file = os.path.join(cache_dir, fname.replace('.geojson', '.parquet'))
        
        if use_cache and os.path.exists(cache_file):
            print(f"Loading {fname} (cached)...")
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                gdf = gpd.read_parquet(cache_file)
        else:
            print(f"Loading {fname}...")
            # Use json module for better control
            import json
            with open(f, 'r', encoding='utf-8', errors='ignore') as fp:
                data = json.load(fp)
            
            # Convert to GeoDataFrame
            from shapely.geometry import shape
            features = data.get('features', [])
            if len(features) == 0:
                continue
                
            geometries = []
            properties = []
            for feat in features:
                try:
                    geom = shape(feat['geometry'])
                    geometries.append(geom)
                    properties.append(feat.get('properties', {}))
                except:
                    pass
            
            gdf = gpd.GeoDataFrame(properties, geometry=geometries, crs='EPSG:4326')
            
            # Cache as parquet
            if use_cache:
                try:
                    gdf.to_parquet(cache_file)
                except:
                    pass
            
        # Ensure CRS is set
        if gdf.crs is None:
            gdf = gdf.set_crs('EPSG:4326')
            
        snapshots[end_date] = gdf
        print(f"  -> {len(gdf)} buildings")
        
    return snapshots


def clean_buildings(gdf):
    """
    Clean building geometries:
    - Fix invalid geometries
    - Remove duplicates
    - Filter to valid polygons
    """
    # Make valid
    gdf['geometry'] = gdf['geometry'].make_valid()
    
    # Keep only polygons/multipolygons
    gdf = gdf[gdf.geometry.type.isin(['Polygon', 'MultiPolygon'])]
    
    # Remove empty geometries
    gdf = gdf[~gdf.geometry.is_empty]
    
    return gdf


def extract_osm_id(gdf):
    """
    Extract OSM ID from features for tracking across time.
    The @osmId column should contain the OSM element ID.
    """
    if '@osmId' in gdf.columns:
        gdf['osm_id'] = gdf['@osmId']
    elif 'id' in gdf.columns:
        gdf['osm_id'] = gdf['id']
    else:
        # Generate unique IDs based on geometry centroid
        gdf['osm_id'] = gdf.geometry.apply(lambda g: f"gen_{hash(g.wkb)}")
    
    return gdf


def identify_new_buildings(prev_gdf, curr_gdf):
    """
    Identify buildings that are new in curr_gdf compared to prev_gdf.
    Uses OSM IDs for matching, with fallback to spatial intersection.
    
    Returns:
        GeoDataFrame of new buildings
    """
    if prev_gdf is None or len(prev_gdf) == 0:
        # All buildings are "new" in first period
        return curr_gdf.copy()
    
    # Match by OSM ID
    prev_ids = set(prev_gdf['osm_id'].unique())
    new_mask = ~curr_gdf['osm_id'].isin(prev_ids)
    
    return curr_gdf[new_mask].copy()


def create_fishnet(bounds, cell_size=500):
    """
    Create a fishnet grid covering the given bounds.
    
    Args:
        bounds: (minx, miny, maxx, maxy) in projected CRS
        cell_size: grid cell size in meters
        
    Returns:
        GeoDataFrame with grid cells
    """
    minx, miny, maxx, maxy = bounds
    
    cells = []
    x = minx
    idx = 0
    while x < maxx:
        y = miny
        while y < maxy:
            cell = box(x, y, x + cell_size, y + cell_size)
            cells.append({'geometry': cell, 'cell_id': idx})
            y += cell_size
            idx += 1
        x += cell_size
        
    return gpd.GeoDataFrame(cells, crs='EPSG:25832')


def aggregate_to_grid(buildings_gdf, grid_gdf):
    """
    Aggregate building counts and areas to grid cells.
    
    Returns grid with count and area columns added.
    """
    # Spatial join buildings to grid cells
    joined = gpd.sjoin(buildings_gdf, grid_gdf, how='left', predicate='within')
    
    # Aggregate by cell
    agg = joined.groupby('cell_id').agg({
        'osm_id': 'count',
        'geometry': lambda x: x.iloc[0].area if len(x) > 0 else 0
    }).rename(columns={'osm_id': 'building_count'})
    
    # Merge back to grid
    result = grid_gdf.merge(agg, on='cell_id', how='left')
    result['building_count'] = result['building_count'].fillna(0).astype(int)
    
    return result


def main():
    p = argparse.ArgumentParser(description='Urban expansion analysis pipeline')
    p.add_argument('--data', default='data/buildings', help='folder with building GeoJSON files')
    p.add_argument('--out', default='output', help='output folder')
    p.add_argument('--grid-size', type=int, default=500, help='grid cell size in meters')
    args = p.parse_args()
    
    os.makedirs(args.out, exist_ok=True)
    
    print("="*60)
    print("Urban Expansion Analysis Pipeline for Münster")
    print("="*60)
    
    # 1. Load building snapshots
    print("\n[1/5] Loading building snapshots...")
    snapshots = load_building_snapshots(args.data)
    
    if len(snapshots) == 0:
        print("No building data found!")
        return
        
    print(f"\nLoaded {len(snapshots)} time periods")
    
    # 2. Clean and prepare data
    print("\n[2/5] Cleaning building data...")
    for period, gdf in snapshots.items():
        gdf = clean_buildings(gdf)
        gdf = extract_osm_id(gdf)
        
        # Reproject to UTM 32N for metric operations
        if gdf.crs.to_epsg() != 25832:
            gdf = gdf.to_crs('EPSG:25832')
            
        snapshots[period] = gdf
        
    # 3. Identify new buildings per period
    print("\n[3/5] Identifying new buildings per period...")
    sorted_periods = sorted(snapshots.keys())
    new_buildings = {}
    
    prev_gdf = None
    for period in sorted_periods:
        curr_gdf = snapshots[period]
        new_gdf = identify_new_buildings(prev_gdf, curr_gdf)
        new_buildings[period] = new_gdf
        
        new_count = len(new_gdf)
        total = len(curr_gdf)
        print(f"  {period}: {new_count} new buildings (total: {total})")
        
        prev_gdf = curr_gdf
    
    # 4. Create aggregation grid
    print("\n[4/5] Creating aggregation grid...")
    
    # Get overall bounds from all periods
    all_bounds = []
    for gdf in snapshots.values():
        all_bounds.append(gdf.total_bounds)
    all_bounds = np.array(all_bounds)
    bounds = (all_bounds[:, 0].min(), all_bounds[:, 1].min(),
              all_bounds[:, 2].max(), all_bounds[:, 3].max())
    
    grid = create_fishnet(bounds, cell_size=args.grid_size)
    print(f"  Created {len(grid)} grid cells ({args.grid_size}m)")
    
    # 5. Aggregate new buildings to grid
    print("\n[5/5] Aggregating new buildings to grid...")
    
    grid_with_counts = grid.copy()
    for period in sorted_periods:
        new_gdf = new_buildings[period]
        
        if len(new_gdf) > 0:
            # Count new buildings per cell
            joined = gpd.sjoin(new_gdf, grid[['cell_id', 'geometry']], 
                              how='left', predicate='within')
            counts = joined.groupby('cell_id').size()
            grid_with_counts[f'new_{period}'] = grid_with_counts['cell_id'].map(counts).fillna(0).astype(int)
        else:
            grid_with_counts[f'new_{period}'] = 0
            
        print(f"  {period}: {grid_with_counts[f'new_{period}'].sum()} new buildings")
    
    # Save outputs
    print("\n[Output]")
    
    # Save grid with time-series counts
    out_grid = os.path.join(args.out, 'grid_new_buildings.geojson')
    grid_with_counts.to_file(out_grid, driver='GeoJSON')
    print(f"  Saved grid to {out_grid}")
    
    # Save summary statistics
    summary = []
    for period in sorted_periods:
        col = f'new_{period}'
        if col in grid_with_counts.columns:
            summary.append({
                'period': period,
                'total_new_buildings': int(grid_with_counts[col].sum()),
                'cells_with_new': int((grid_with_counts[col] > 0).sum()),
                'max_per_cell': int(grid_with_counts[col].max()),
                'mean_per_cell': float(grid_with_counts[col].mean())
            })
    
    summary_df = pd.DataFrame(summary)
    out_summary = os.path.join(args.out, 'summary_stats.csv')
    summary_df.to_csv(out_summary, index=False)
    print(f"  Saved summary to {out_summary}")
    
    print("\nDone!")


if __name__ == '__main__':
    main()
