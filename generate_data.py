"""Genera datos sintéticos de e-commerce en Parquet, por chunks (no carga todo en RAM).

Uso: python generate_data.py --rows 10_000_000
"""
import argparse
from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

DATA = Path(__file__).parent / "data"
COUNTRIES = ["AR", "BR", "CL", "CO", "MX", "PE", "UY", "ES", "FR", "DE"]
SEGMENTS = ["consumer", "smb", "enterprise"]
STATUSES = ["completed", "completed", "completed", "cancelled", "refunded"]
CHUNK = 2_000_000


def main(rows: int, customers: int = 500_000, seed: int = 42) -> None:
    DATA.mkdir(exist_ok=True)
    rng = np.random.default_rng(seed)

    # Dimensión: customers
    pq.write_table(
        pa.table({
            "customer_id": np.arange(customers, dtype=np.int64),
            "country": rng.choice(COUNTRIES, customers),
            "segment": rng.choice(SEGMENTS, customers),
        }),
        DATA / "customers.parquet",
    )

    # Hechos: orders, escritos por chunks
    start = np.datetime64("2022-01-01T00:00:00")
    seconds_span = 3 * 365 * 24 * 3600
    path = DATA / f"orders_{rows}.parquet"
    writer, written = None, 0
    while written < rows:
        n = min(CHUNK, rows - written)
        table = pa.table({
            "order_id": np.arange(written, written + n, dtype=np.int64),
            "customer_id": rng.integers(0, customers, n, dtype=np.int64),
            "order_ts": start + rng.integers(0, seconds_span, n).astype("timedelta64[s]"),
            "quantity": rng.integers(1, 6, n, dtype=np.int32),
            "unit_price": np.round(rng.gamma(2.0, 25.0, n), 2),
            "discount": np.round(rng.choice([0, 0.05, 0.1, 0.2], n), 2),
            "status": rng.choice(STATUSES, n),
            # columnas "de relleno" que el pipeline NO usa (realismo: tablas anchas)
            "notes": rng.choice(["", "gift", "express", "fragile", "call before"], n),
            "channel": rng.choice(["web", "app", "store", "partner"], n),
        })
        writer = writer or pq.ParquetWriter(path, table.schema)
        writer.write_table(table)
        written += n
        print(f"  {written:,}/{rows:,}")
    writer.close()
    print(f"OK -> {path} ({path.stat().st_size / 1e6:.0f} MB)")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--rows", type=lambda s: int(s.replace("_", "")), default=10_000_000)
    main(p.parse_args().rows)
