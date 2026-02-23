"""
Fetch semiannual OSM building footprints from OHSOME API for Münster.

This script fetches building footprints for each 6-month period and saves
GeoJSON results.

Usage:
    python scripts/ohsome_fetch.py --start 2015-01-01 --end 2025-01-01 --out data/buildings
"""
import argparse
import os
import json
import time
import requests
from datetime import datetime, timedelta

# Ohsome API endpoint for building geometries
OHSOME_ENDPOINT = "https://api.ohsome.org/v1/elements/geometry"

# Münster bounding box (minLon, minLat, maxLon, maxLat)
MUENSTER_BBOX = "7.47,51.84,7.77,52.06"


def generate_periods(start_date, end_date, months=6):
    """Generate semiannual time periods as list of (start, end) tuples."""
    periods = []
    cur = start_date
    while cur < end_date:
        nxt = cur + timedelta(days=months * 30)
        if nxt > end_date:
            nxt = end_date
        periods.append((cur.strftime('%Y-%m-%d'), nxt.strftime('%Y-%m-%d')))
        cur = nxt
    return periods


def fetch_buildings(bbox, timestamp, timeout=600):
    """
    Fetch building geometries from ohsome API for a single timestamp.
    Returns GeoJSON dict.
    """
    data = {
        'bboxes': bbox,
        'time': timestamp,
        'filter': 'building=*',
        'properties': 'tags',
    }
    
    response = requests.post(OHSOME_ENDPOINT, data=data, timeout=timeout)
    
    if response.status_code == 200:
        return response.json()
    else:
        raise Exception(f"API error {response.status_code}: {response.text[:500]}")


def save_geojson(data, out_path):
    """Save GeoJSON data to file."""
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False)


def main():
    p = argparse.ArgumentParser(description='Fetch OSM building footprints from ohsome API')
    p.add_argument('--start', required=True, help='start date YYYY-MM-DD')
    p.add_argument('--end', required=True, help='end date YYYY-MM-DD')
    p.add_argument('--out', default='data/buildings', help='output folder for results')
    p.add_argument('--bbox', default=MUENSTER_BBOX, help='bbox as minLon,minLat,maxLon,maxLat')
    p.add_argument('--delay', type=float, default=5.0, help='delay between API calls (seconds)')
    args = p.parse_args()

    start = datetime.fromisoformat(args.start)
    end = datetime.fromisoformat(args.end)

    os.makedirs(args.out, exist_ok=True)

    print(f"Fetching building footprints for bbox: {args.bbox}")
    print(f"Time range: {args.start} to {args.end}")
    
    periods = generate_periods(start, end, months=6)
    print(f"Total periods: {len(periods)}")
    
    for i, (s, e) in enumerate(periods, start=1):
        out_path = os.path.join(args.out, f'buildings_{i:03d}_{s}_to_{e}.geojson')
        
        # Skip if already downloaded and valid
        if os.path.exists(out_path) and os.path.getsize(out_path) > 100:
            print(f"[{i}/{len(periods)}] Skipping {s} to {e} (already exists)")
            continue
            
        print(f"[{i}/{len(periods)}] Fetching {s} to {e}...")
        
        try:
            # Fetch buildings at end of period (snapshot)
            geojson = fetch_buildings(args.bbox, e)
            save_geojson(geojson, out_path)
            
            feature_count = len(geojson.get('features', []))
            print(f"  -> Saved {feature_count} buildings to {out_path}")
            
            # Rate limiting
            if i < len(periods):
                time.sleep(args.delay)
                
        except Exception as ex:
            print(f"  -> Error: {ex}")
            error_path = out_path.replace('.geojson', '.error.txt')
            with open(error_path, 'w') as f:
                f.write(str(ex))

    print('\nDone!')


if __name__ == '__main__':
    main()
