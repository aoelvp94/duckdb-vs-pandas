"""Mismo pipeline en SQL. DuckDB optimiza solo: proyección, pushdown, join, paralelismo."""
import duckdb

QUERY = """
SELECT
    c.country,
    strftime(o.order_ts, '%Y-%m')                       AS month,
    count(*)                                            AS orders,
    sum(o.quantity * o.unit_price * (1 - o.discount))   AS revenue,
    avg(o.quantity * o.unit_price * (1 - o.discount))   AS avg_ticket
FROM read_parquet('{orders}') AS o
JOIN read_parquet('{customers}') AS c USING (customer_id)
WHERE o.status = 'completed'
  AND o.order_ts >= TIMESTAMP '2023-01-01'
GROUP BY ALL
ORDER BY c.country, month
"""


def run(orders_path: str, customers_path: str) -> list[tuple]:
    con = duckdb.connect()  # en memoria; no hay servidor ni setup
    return con.sql(QUERY.format(orders=orders_path, customers=customers_path)).fetchall()
