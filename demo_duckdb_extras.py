"""Dos momentos 'wow' para la demo, sobre los mismos datos del benchmark.

Uso:
  python demo_duckdb_extras.py explain --rows 10_000_000
  python demo_duckdb_extras.py spill   --rows 10_000_000 --memory 500MB
"""
import argparse
import tempfile
from pathlib import Path

import duckdb

DATA = Path(__file__).parent / "data"

QUERY = """
SELECT c.country, strftime(o.order_ts, '%Y-%m') AS month, count(*) AS orders,
       sum(o.quantity * o.unit_price * (1 - o.discount)) AS revenue
FROM read_parquet('{orders}') AS o
JOIN read_parquet('{customers}') AS c USING (customer_id)
WHERE o.status = 'completed' AND o.order_ts >= TIMESTAMP '2023-01-01'
GROUP BY ALL ORDER BY c.country, month
"""


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("mode", choices=["explain", "spill"])
    p.add_argument("--rows", type=lambda s: int(s.replace("_", "")), default=10_000_000)
    p.add_argument("--memory", default="500MB", help="límite de memoria para el modo spill")
    a = p.parse_args()

    orders = DATA / f"orders_{a.rows}.parquet"
    customers = DATA / "customers.parquet"
    if not orders.exists():
        raise SystemExit(f"Falta {orders}. Corré: python generate_data.py --rows {a.rows}")
    sql = QUERY.format(orders=orders, customers=customers)

    con = duckdb.connect()
    if a.mode == "explain":
        # Buscá el filtro y la lista de columnas DENTRO del scan de Parquet:
        # eso es predicate + projection pushdown, sin escribir una línea de código.
        print(con.sql("EXPLAIN " + sql).fetchall()[0][1])
    else:
        with tempfile.TemporaryDirectory() as tmp:
            con.execute(f"SET memory_limit='{a.memory}'")
            con.execute(f"SET temp_directory='{tmp}'")
            rows = con.sql(sql).fetchall()
            print(f"OK con memory_limit={a.memory}: {len(rows)} filas de resultado")


if __name__ == "__main__":
    main()
