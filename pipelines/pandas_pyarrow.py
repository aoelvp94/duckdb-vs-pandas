"""pandas optimizado sobre PyArrow: el escalón intermedio entre pandas 'naive' y DuckDB.

Todo lo que hace DuckDB solo, acá hay que escribirlo a mano:
  1. Projection pushdown: se leen solo las columnas necesarias.
  2. Predicate pushdown: el filtro se aplica DURANTE la lectura del Parquet (pyarrow.dataset).
  3. Filtrar ANTES del join, y el join corre en Arrow (multihilo), sin pasar por pandas.
  4. dtype_backend="pyarrow": los tipos quedan en Arrow, sin conversión a NumPy/object.
"""
from datetime import datetime

import pandas as pd
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.dataset as ds
import pyarrow.parquet as pq

ORDER_COLUMNS = ["order_id", "customer_id", "order_ts", "quantity", "unit_price", "discount"]


def run(orders_path: str, customers_path: str) -> list[tuple]:
    orders = ds.dataset(orders_path, format="parquet")

    # Scalar con el mismo tipo/unidad que la columna, para que la comparación sea exacta.
    since = pa.scalar(datetime(2023, 1, 1), type=orders.schema.field("order_ts").type)
    predicate = (pc.field("status") == "completed") & (pc.field("order_ts") >= since)

    # `status` se usa en el filtro pero no se proyecta: nunca llega a memoria.
    filtered = orders.to_table(columns=ORDER_COLUMNS, filter=predicate)
    customers = pq.read_table(customers_path, columns=["customer_id", "country"])
    joined = filtered.join(customers, keys="customer_id", join_type="inner")

    df = joined.to_pandas(types_mapper=pd.ArrowDtype)
    df["net"] = df["quantity"] * df["unit_price"] * (1 - df["discount"])
    df["month"] = df["order_ts"].dt.strftime("%Y-%m")
    out = (
        df.groupby(["country", "month"])
        .agg(orders=("order_id", "count"), revenue=("net", "sum"), avg_ticket=("net", "mean"))
        .reset_index()
        .sort_values(["country", "month"])
    )
    # Casts explícitos: con ArrowDtype los escalares no son float/int de Python.
    return [
        (str(r.country), str(r.month), int(r.orders), float(r.revenue), float(r.avg_ticket))
        for r in out.itertuples(index=False)
    ]
