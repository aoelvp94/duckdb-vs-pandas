"""Corre cada pipeline en un subproceso aislado, valida que den lo mismo y arma la tabla.

Uso: python benchmark.py --rows 10_000_000 [--repeat 3]

Además de imprimir la tabla, guarda results/benchmark_<rows>.md con la máquina y las
versiones usadas, listo para pegar en BENCHMARK.md o proyectar en clase.
"""
import argparse
import json
import math
import os
import platform
import statistics
import subprocess
import sys
from importlib import metadata
from pathlib import Path

ENGINES = ["pandas_naive", "pandas_tuned", "pandas_pyarrow", "duckdb_sql"]
LABELS = {
    "pandas_naive": "pandas naive (lee todo, join antes de filtrar)",
    "pandas_tuned": "pandas tuned (columnas + filtros en la lectura)",
    "pandas_pyarrow": "pandas + PyArrow (pushdown y join en Arrow)",
    "duckdb_sql": "DuckDB (SQL)",
}
ROOT = Path(__file__).parent
DATA = ROOT / "data"


def run_engine(engine: str, orders: Path, customers: Path) -> dict | None:
    proc = subprocess.run([sys.executable, "run_one.py", engine, str(orders), str(customers)],
                          capture_output=True, text=True, cwd=ROOT)
    if proc.returncode != 0:  # típico: MemoryError / OOM-killer en pandas
        tail = (proc.stderr or "").strip().splitlines()[-1:] or ["sin detalle"]
        print(f"  [{engine}] falló (exit {proc.returncode}): {tail[0]}", file=sys.stderr)
        return None
    return json.loads(proc.stdout.strip().splitlines()[-1])


def same_result(a: list, b: list) -> bool:
    return len(a) == len(b) and all(
        x[0] == y[0] and x[1] == y[1] and x[2] == y[2]
        and math.isclose(x[3], y[3], rel_tol=1e-6) and math.isclose(x[4], y[4], rel_tol=1e-6)
        for x, y in zip(a, b)
    )


def environment() -> dict:
    def ver(pkg: str) -> str:
        try:
            return metadata.version(pkg)
        except metadata.PackageNotFoundError:
            return "n/d"

    try:
        ram_gb = os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") / 1e9
    except (ValueError, OSError, AttributeError):
        ram_gb = float("nan")
    return {
        "os": f"{platform.system()} {platform.release()} ({platform.machine()})",
        "cpus": os.cpu_count(),
        "ram_gb": round(ram_gb, 1),
        "python": platform.python_version(),
        "duckdb": ver("duckdb"),
        "pandas": ver("pandas"),
        "pyarrow": ver("pyarrow"),
    }


def main(rows: int, repeat: int) -> None:
    orders, customers = DATA / f"orders_{rows}.parquet", DATA / "customers.parquet"
    if not orders.exists():
        sys.exit(f"Falta {orders}. Corré: python generate_data.py --rows {rows}")

    results, reference = {}, None
    for engine in ENGINES:
        print(f"-> {engine} ({repeat} corridas)...", file=sys.stderr)
        runs = [run_engine(engine, orders, customers) for _ in range(repeat)]
        if any(r is None for r in runs):
            results[engine] = None
            continue
        results[engine] = {"seconds": statistics.median(r["seconds"] for r in runs),
                           "peak_mb": max(r["peak_mb"] for r in runs)}
        reference = reference or runs[0]["rows"]
        assert same_result(reference, runs[0]["rows"]), f"{engine} da otro resultado!"

    base = results.get("pandas_naive")
    env = environment()
    header = f"{rows:,} filas | mediana de {repeat} corridas | resultados verificados idénticos"

    lines = [f"{'engine':<16}{'tiempo (s)':>12}{'pico RAM (MB)':>16}{'speedup':>10}"]
    md = ["| Engine | Tiempo (s) | Pico RAM (MB) | Speedup vs naive |", "|---|---:|---:|---:|"]
    for engine, r in results.items():
        if r is None:
            lines.append(f"{engine:<16}{'FALLÓ (sin memoria u otro error)':>38}")
            md.append(f"| {LABELS[engine]} | falló | falló | - |")
            continue
        speed = f"{base['seconds'] / r['seconds']:.1f}x" if base else "-"
        lines.append(f"{engine:<16}{r['seconds']:>12.2f}{r['peak_mb']:>16,}{speed:>10}")
        md.append(f"| {LABELS[engine]} | {r['seconds']:.2f} | {r['peak_mb']:,} | {speed} |")

    print(f"\n{header}\n")
    print("\n".join(lines))

    out_dir = ROOT / "results"
    out_dir.mkdir(exist_ok=True)
    report = (
        f"### {rows:,} filas\n\n"
        f"- Máquina: {env['os']}, {env['cpus']} CPUs, {env['ram_gb']} GB RAM\n"
        f"- Versiones: Python {env['python']}, DuckDB {env['duckdb']}, "
        f"pandas {env['pandas']}, PyArrow {env['pyarrow']}\n"
        f"- Método: mediana de {repeat} corridas, cada una en un proceso nuevo; "
        f"resultados verificados idénticos entre engines\n\n"
        + "\n".join(md) + "\n"
    )
    path = out_dir / f"benchmark_{rows}.md"
    path.write_text(report)
    print(f"\nReporte guardado en {path.relative_to(ROOT)}")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--rows", type=lambda s: int(s.replace("_", "")), default=10_000_000)
    p.add_argument("--repeat", type=int, default=3)
    a = p.parse_args()
    main(a.rows, a.repeat)
