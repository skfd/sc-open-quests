"""Pull Overture divisions into parquet files for tools/places.py.

Usage:
  overture_pull.py RELEASE CC...                 # countries, full rows with geometry -> data/overture/
  overture_pull.py RELEASE --world [--out DIR]   # the world, no polygons -> data/overture/world/

The world pull keeps every division column but geometry (division.parquet) and, from division_area,
only the columns tools/places.py needs: division_id, class, subtype, country, bbox (division_area.parquet).
A division's own bbox is its label point; the area's bbox is the one places.py publishes.
Needs duckdb (the .scratch/overture venv), network access to the public Overture S3 bucket.
"""
import os, sys, time
import duckdb

args = sys.argv[1:]
if not args:
    sys.exit(__doc__)
rel, rest = args[0], args[1:]
world = "--world" in rest
out = None
if "--out" in rest:
    out = rest[rest.index("--out") + 1]
ccs = [a for a in rest if not a.startswith("--") and a != out]
out = out or ("data/overture/world" if world else "data/overture")
os.makedirs(out, exist_ok=True)

con = duckdb.connect()
con.execute("INSTALL httpfs; LOAD httpfs; INSTALL spatial; LOAD spatial; SET s3_region='us-west-2';")
base = f"s3://overturemaps-us-west-2/release/{rel}/theme=divisions"

if world:
    queries = {
        "division": f"SELECT * EXCLUDE (geometry) FROM read_parquet('{base}/type=division/*', hive_partitioning=1)",
        "division_area": f"SELECT division_id, class, subtype, country, bbox FROM read_parquet('{base}/type=division_area/*', hive_partitioning=1)",
    }
else:
    inlist = ",".join(f"'{c}'" for c in ccs)
    queries = {t: f"SELECT * FROM read_parquet('{base}/type={t}/*', hive_partitioning=1) WHERE country IN ({inlist})"
               for t in ("division", "division_area")}

for t, q in queries.items():
    t0 = time.time()
    path = f"{out}/{t}.parquet".replace("\\", "/")
    con.execute(f"COPY ({q}) TO '{path}' (FORMAT parquet)")
    n = con.execute(f"SELECT count(*) FROM '{path}'").fetchone()[0]
    print(t, n, f"{time.time()-t0:.0f}s", path, flush=True)
