# DuckDB vs pandas: mismo pipeline, dos mundos

MWE para clase: el mismo pipeline (filtro → join → agregación mensual por país)
implementado en **pandas "naive"**, **pandas "tuned"**, **pandas + PyArrow** y **DuckDB (SQL)**,
corrido en procesos aislados para comparar **tiempo** y **pico de RAM**.

> Requiere Python >= 3.11 (DuckDB 2.0 y pandas 3.0).

## Correrlo

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

python generate_data.py --rows 10_000_000     # ~ 300-400 MB en Parquet
python benchmark.py --rows 10_000_000 --repeat 3
```

Probá escalar: `1_000_000`, `10_000_000`, `50_000_000`. Con tu RAM como límite,
pandas_naive va a fallar antes que los otros: ese es el punto de la demo.

## Qué mostrar a los alumnos

| Idea | Dónde se ve |
|---|---|
| **Projection pushdown**: DuckDB lee solo las columnas que usa la query | `pandas_naive` carga las 9 columnas, `duckdb_sql` solo 6 |
| **Predicate pushdown**: filtra mientras lee Parquet | `pandas_tuned` lo imita a mano con `filters=` |
| **Optimizador de queries**: reordena filtro y join por vos | en pandas el orden de tus líneas *es* el plan |
| **Ejecución columnar, vectorizada y paralela** | DuckDB usa todos los cores por defecto |
| **Sin copias intermedias**: pandas materializa cada DataFrame | mirá el pico de RAM |
| **Zero setup**: sin servidor, `pip install duckdb` | `duckdb.connect()` |

## Ojo: pandas 3.x
Con pandas 3 las columnas de texto usan el dtype `str` (respaldado por PyArrow) y rige
Copy-on-Write, así que `pandas_naive` consume menos RAM en strings que con pandas 2. La brecha
con DuckDB se achica ahí, pero no en lo estructural: lectura de columnas innecesarias,
un solo hilo y copias intermedias. Buen momento para que los alumnos lo midan en vez de creerlo.

## Ejercicios extra

1. Corré DuckDB con límite de memoria: `con.execute("SET memory_limit='1GB'")` y
   comprobá que sigue funcionando sobre datos más grandes que la RAM (spill a disco).
2. Mirá el plan: `con.sql("EXPLAIN " + QUERY...)` y buscá el filtro dentro del `PARQUET_SCAN`.
3. Reescribí `pandas_tuned` hasta alcanzar a DuckDB. Cuánto código manual hizo falta?

## Honestidad en el benchmark

- Cada engine corre en un **subproceso nuevo** (sin cache de imports ni heap sucio).
- Se **verifica que los resultados sean idénticos** antes de comparar tiempos.
- Hay una versión pandas optimizada para no comparar contra un hombre de paja.
- pandas sigue siendo excelente para exploración interactiva y datos chicos:
  la conclusión es "elegí la herramienta según el tamaño y el tipo de trabajo".

## Codespaces
Abrí el repo en GitHub → **Code → Codespaces → Create**: el devcontainer instala todo.

## Licencia
MIT (ver `LICENSE`).

## Documentación

| Archivo | Para qué |
|---|---|
| [`BENCHMARK.md`](BENCHMARK.md) | Qué mide el benchmark, cómo, limitaciones y dónde pegar tus resultados |
| [`DEMO.md`](DEMO.md) | Guion paso a paso de la demo (15-20 min) |
| `demo_duckdb_extras.py` | `explain` (plan con pushdown) y `spill` (límite de memoria) para la demo |
| `results/` | Reportes generados por `benchmark.py` (máquina, versiones, tabla) |

El segundo repo, `airflow-duckdb-dbt-demo`, repite el pipeline orquestado con Airflow (Astro CLI) y dbt.
