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
# ru_maxrss: bytes en macOS, KiB en Linux (y en Docker). Lo pasamos a MB (10^6 bytes).
peak_mb = peak / 1e6 if sys.platform == "darwin" else peak * 1024 / 1e6

print(json.dumps({"engine": engine, "seconds": round(elapsed, 2),
                  "peak_mb": round(peak_mb), "rows": rows}))
