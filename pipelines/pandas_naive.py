"""Pipeline 'como lo escribe un junior': leer todo, filtrar después."""
import pandas as pd


def run(orders_path: str, customers_path: str) -> list[tuple]:
    orders = pd.read_parquet(orders_path)          # carga TODAS las columnas y filas
    customers = pd.read_parquet(customers_path)

    df = orders.merge(customers, on="customer_id")  # join antes de filtrar
    df = df[(df["status"] == "completed") & (df["order_ts"] >= "2023-01-01")]
    df["net"] = df["quantity"] * df["unit_price"] * (1 - df["discount"])
    df["month"] = df["order_ts"].dt.to_period("M").astype(str)

    out = (
        df.groupby(["country", "month"])
        .agg(orders=("order_id", "count"), revenue=("net", "sum"), avg_ticket=("net", "mean"))
        .reset_index()
        .sort_values(["country", "month"])
    )
    return list(out.itertuples(index=False, name=None))
