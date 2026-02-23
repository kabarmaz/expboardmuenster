Project scaffold for Urban Expansion Forecasting (Münster)

What I created:
- `requirements.txt` — Python deps for ingestion, EDA, forecasting, and DL.
- `scripts/ohsome_fetch.py` — scaffold to prepare semiannual ohsome requests and emit curl commands.

Quick start (Windows PowerShell):

1) Create a venv and install deps

```powershell
python -m venv .venv
.\.venv\Scripts\activate
python -m pip install -r requirements.txt
```

2) Prepare an AOI GeoJSON at `data/muenster_boundary.geojson` (optional). If absent, script will ask for bbox.

3) Generate semiannual payloads and curl commands:

```powershell
python scripts\ohsome_fetch.py --start 2015-01-01 --end 2025-01-01 --out requests
```

That writes payload JSON files to `requests/` and prints example `curl` commands you can run.

Next steps I can take (pick one):
- Run ingestion and fetch building snapshots (requires AOI or bbox)
- Build aggregation grid and run EDA
- Prototype forecasting models
