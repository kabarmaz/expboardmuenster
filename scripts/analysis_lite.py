"""
Urban Expansion Analysis Pipeline for Münster - Memory Efficient Version.

This script processes building data incrementally to track new buildings.
"""
import argparse
import os
import glob
import json
import pandas as pd
import geopandas as gpd
import numpy as np
from shapely.geometry import box, shape
from pathlib import Path
from collections import defaultdict


def extract_building_ids(geojson_path):
    """
    Extract building OSM IDs from a GeoJSON file using streaming parser.
    Returns set of OSM IDs.
    """
    import ijson
    print(f"  Extracting IDs from {os.path.basename(geojson_path)}...")
    
    ids = set()
    with open(geojson_path, 'rb') as f:
        for item in ijson.items(f, 'features.item'):
            props = item.get('properties', {})
            osm_id = props.get('@osmId') or props.get('osmId') or props.get('id')
            if osm_id:
                ids.add(str(osm_id))
    
    return ids


def load_building_geometries(geojson_path, osm_ids=None):
    """
    Load building geometries, optionally filtering by OSM IDs.
    Returns GeoDataFrame.
    """
    print(f"  Loading geometries from {os.path.basename(geojson_path)}...")
    
    with open(geojson_path, 'r', encoding='utf-8', errors='ignore') as f:
        data = json.load(f)
    
    geometries = []
    properties = []
    
    for feat in data.get('features', []):
        try:
            props = feat.get('properties', {})
            osm_id = str(props.get('@osmId') or props.get('osmId') or props.get('id', ''))
            
            # Filter by IDs if specified
            if osm_ids is not None and osm_id not in osm_ids:
                continue
                
            geom = shape(feat['geometry'])
            if geom.is_valid and not geom.is_empty:
                geometries.append(geom)
                properties.append({
                    'osm_id': osm_id,
                    'building': props.get('building', 'yes'),
                    'area_m2': geom.area if geom.geom_type in ['Polygon', 'MultiPolygon'] else 0
                })
        except:
            pass
    
    if len(geometries) == 0:
        return gpd.GeoDataFrame(columns=['osm_id', 'building', 'area_m2', 'geometry'], crs='EPSG:4326')
    
    gdf = gpd.GeoDataFrame(properties, geometry=geometries, crs='EPSG:4326')
    return gdf


def create_fishnet(bounds, cell_size=500, crs='EPSG:25832'):
    """
    Create a fishnet grid covering the given bounds.
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
        
    return gpd.GeoDataFrame(cells, crs=crs)


def main():
    p = argparse.ArgumentParser(description='Urban expansion analysis')
    p.add_argument('--data', default='data/buildings', help='folder with building GeoJSON files')
    p.add_argument('--out', default='output', help='output folder')
    p.add_argument('--grid-size', type=int, default=500, help='grid cell size in meters')
    args = p.parse_args()
    
    os.makedirs(args.out, exist_ok=True)
    
    print("="*60)
    print("Urban Expansion Analysis - Memory Efficient Version")
    print("="*60)
    
    # Get list of files
    files = sorted(glob.glob(os.path.join(args.data, 'buildings_*.geojson')))
    print(f"\nFound {len(files)} building snapshots")
    
    if len(files) == 0:
        print("No files found!")
        return
    
    # Step 1: Extract IDs from all periods to find new buildings
    print("\n[1/4] Extracting building IDs from all periods...")
    
    period_ids = {}
    for f in files:
        fname = os.path.basename(f)
        parts = fname.replace('.geojson', '').split('_')
        period = parts[4] if len(parts) >= 5 else parts[-1]
        
        ids = extract_building_ids(f)
        period_ids[period] = (f, ids)
        print(f"  {period}: {len(ids)} buildings")
    
    # Step 2: Identify new buildings per period
    print("\n[2/4] Identifying new buildings per period...")
    
    sorted_periods = sorted(period_ids.keys())
    new_building_counts = {}
    new_ids_per_period = {}
    
    prev_ids = set()
    for period in sorted_periods:
        filepath, curr_ids = period_ids[period]
        new_ids = curr_ids - prev_ids
        new_building_counts[period] = len(new_ids)
        new_ids_per_period[period] = (filepath, new_ids)
        print(f"  {period}: {len(new_ids)} new buildings (total: {len(curr_ids)})")
        prev_ids = curr_ids
    
    # Step 3: Create summary
    print("\n[3/4] Creating summary statistics...")
    
    summary = []
    for period in sorted_periods:
        filepath, curr_ids = period_ids[period]
        new_count = new_building_counts[period]
        summary.append({
            'period_end': period,
            'total_buildings': len(curr_ids),
            'new_buildings': new_count,
            'cumulative_growth': len(curr_ids)
        })
    
    summary_df = pd.DataFrame(summary)
    summary_path = os.path.join(args.out, 'building_growth_summary.csv')
    summary_df.to_csv(summary_path, index=False)
    print(f"  Saved: {summary_path}")
    
    # Step 4: Load new building geometries and aggregate to grid for most recent periods
    print("\n[4/4] Processing new building geometries for recent periods...")
    
    # Process last 5 periods for grid aggregation (to save memory)
    recent_periods = sorted_periods[-5:] if len(sorted_periods) >= 5 else sorted_periods
    
    # Load first file to get bounding box
    sample_gdf = load_building_geometries(files[0])
    sample_gdf = sample_gdf.to_crs('EPSG:25832')
    bounds = sample_gdf.total_bounds
    
    # Add some buffer
    buffer = 1000
    bounds = (bounds[0] - buffer, bounds[1] - buffer, bounds[2] + buffer, bounds[3] + buffer)
    
    # Create grid
    grid = create_fishnet(bounds, cell_size=args.grid_size)
    print(f"  Created grid with {len(grid)} cells ({args.grid_size}m)")
    
    # Process each recent period
    for period in recent_periods:
        filepath, new_ids = new_ids_per_period[period]
        
        if len(new_ids) == 0:
            grid[f'new_{period}'] = 0
            continue
        
        # Load only the new building geometries
        new_gdf = load_building_geometries(filepath, osm_ids=new_ids)
        
        if len(new_gdf) > 0:
            new_gdf = new_gdf.to_crs('EPSG:25832')
            
            # Spatial join with grid
            joined = gpd.sjoin(new_gdf, grid[['cell_id', 'geometry']], 
                              how='left', predicate='within')
            counts = joined.groupby('cell_id').size()
            grid[f'new_{period}'] = grid['cell_id'].map(counts).fillna(0).astype(int)
        else:
            grid[f'new_{period}'] = 0
        
        print(f"  {period}: aggregated {len(new_ids)} new buildings to grid")
    
    # Save grid
    grid_path = os.path.join(args.out, 'grid_new_buildings.geojson')
    grid.to_file(grid_path, driver='GeoJSON')
    print(f"  Saved: {grid_path}")
    
    # Print growth summary
    print("\n" + "="*60)
    print("Urban Growth Summary (2015-2025)")
    print("="*60)
    print(summary_df.to_string(index=False))
    
    total_growth = summary_df['new_buildings'].sum()
    first_count = summary_df.iloc[0]['total_buildings']
    last_count = summary_df.iloc[-1]['total_buildings']
    pct_growth = (last_count - first_count) / first_count * 100
    
    print(f"\n10-Year Summary:")
    print(f"  Total new buildings: {total_growth:,}")
    print(f"  2015 stock: {first_count:,}")
    print(f"  2025 stock: {last_count:,}")
    print(f"  Growth: {pct_growth:.1f}%")
    
    print("\nDone!")


if __name__ == '__main__':
    main()
