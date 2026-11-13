"""Pandas 'bien hecho': solo columnas necesarias + filtro en la lectura (predicate pushdown)."""
import pandas as pd


def run(orders_path: str, customers_path: str) -> list[tuple]:
    orders = pd.read_parquet(
        orders_path,
        columns=["order_id", "customer_id", "order_ts", "quantity", "unit_price", "discount"],
        filters=[("status", "==", "completed"), ("order_ts", ">=", pd.Timestamp("2023-01-01"))],
    )
    customers = pd.read_parquet(customers_path, columns=["customer_id", "country"])

    df = orders.merge(customers, on="customer_id")
    df["net"] = df["quantity"] * df["unit_price"] * (1 - df["discount"])
    df["month"] = df["order_ts"].dt.to_period("M").astype(str)

    out = (
        df.groupby(["country", "month"])
        .agg(orders=("order_id", "count"), revenue=("net", "sum"), avg_ticket=("net", "mean"))
        .reset_index()
        .sort_values(["country", "month"])
    )
    return list(out.itertuples(index=False, name=None))
