"""Ejecuta UN pipeline en un proceso limpio y reporta tiempo y pico de memoria (JSON)."""
import importlib
import json
import resource
import sys
import time

engine, orders, customers = sys.argv[1:4]
module = importlib.import_module(f"pipelines.{engine}")

t0 = time.perf_counter()
rows = module.run(orders, customers)
elapsed = time.perf_counter() - t0

peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
peak_mb = peak / 1e6 if sys.platform == "darwin" else peak / 1e3  # mac: bytes, linux: KB

print(json.dumps({"engine": engine, "seconds": round(elapsed, 2),
                  "peak_mb": round(peak_mb), "rows": rows}))
