"""Pull Overture divisions for some countries into data/overture/ (spike). Usage: pull.py RELEASE CC..."""
import sys, time, duckdb
rel, ccs = sys.argv[1], sys.argv[2:]
con = duckdb.connect()
con.execute("INSTALL httpfs; LOAD httpfs; INSTALL spatial; LOAD spatial; SET s3_region='us-west-2';")
base = f"s3://overturemaps-us-west-2/release/{rel}/theme=divisions"
inlist = ",".join(f"'{c}'" for c in ccs)
for t in ("division", "division_area"):
    t0 = time.time()
    con.execute(f"""COPY (SELECT * FROM read_parquet('{base}/type={t}/*', hive_partitioning=1)
                 WHERE country IN ({inlist})) TO 'data/overture/{t}.parquet' (FORMAT parquet)""")
    n = con.execute(f"SELECT count(*) FROM 'data/overture/{t}.parquet'").fetchone()[0]
    print(t, n, f"{time.time()-t0:.0f}s", flush=True)
