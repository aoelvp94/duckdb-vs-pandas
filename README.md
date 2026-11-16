# DuckDB vs pandas: mismo pipeline, dos mundos

MWE: el mismo pipeline (filtro → join → agregación mensual por país)
implementado en **pandas "naive"**, **pandas "tuned"**, **pandas + PyArrow** y **DuckDB (SQL)**,
corrido en procesos aislados para comparar **tiempo** y **pico de RAM**.

> **Para correr la demo y ver los resultados por tu cuenta**, seguí **[GUIA.md](GUIA.md)**:
> instalación por sistema operativo y paso a paso. Solo necesitás Docker.
>
> Método y resultados medidos: [BENCHMARK.md](BENCHMARK.md). Guion para presentarla en vivo
> (15-20 min): [DEMO.md](DEMO.md).

> Solo necesitás **Docker**: nada de Python, venv ni pip en tu máquina. Las dependencias
> (DuckDB 2.0, pandas 3.0, PyArrow) las instala `uv` dentro de la imagen.

## Requisitos

- **Docker**: Docker Desktop (Mac/Windows) o Docker Engine (Linux).
- **Recursos para Docker** (en Docker Desktop: Settings → Resources): con **4 GB** alcanza para
  1M y 10M filas (`pandas_naive` pide ~2.4 GB a 10M). Para 50M, cuantos más GB mejor: con 7.7 GB
  `pandas_naive` igual se queda sin memoria, y eso es parte de la demo.
- **Windows**: usá **WSL2** (Ubuntu) y corré todo desde la terminal de WSL, con el repo clonado
  dentro de WSL (`~/...`, no en `/mnt/c/...`, que es mucho más lento). El `alias dvp` es de
  bash/zsh y no funciona en PowerShell ni en cmd.
- **Linux**: los archivos que crea el contenedor en `data/` y `results/` quedan a nombre de root.
  Para borrarlos: `sudo rm -rf data/*.parquet results`.
- **La primera vez**: `docker build` baja la imagen base y las dependencias. Necesita internet
  y, con una conexión lenta, puede tardar más de 10 minutos (medido: 12.5 min sin caché).
  Hacelo una vez antes de empezar; las siguientes veces usa el caché y tarda segundos.

## Correrlo

```bash
docker build -t duckdb-vs-pandas .
alias dvp='docker run --rm -v "$PWD/data:/app/data" -v "$PWD/results:/app/results" duckdb-vs-pandas'

dvp python generate_data.py --rows 10_000_000     # ~200 MB en Parquet
dvp python benchmark.py --rows 10_000_000 --repeat 3
```

Probá escalar: `1_000_000`, `10_000_000`, `50_000_000`. Con tu RAM como límite,
pandas_naive va a fallar antes que los otros: ese es el punto de la demo.

## Resultados (resumen)

Medido en un Apple M4 con Docker Desktop (10 CPUs, 7.7 GiB para la VM). Tablas completas,
versiones y método en [BENCHMARK.md](BENCHMARK.md#resultados).

| Filas | pandas naive | pandas tuned | pandas + PyArrow | DuckDB |
|---|---:|---:|---:|---:|
| 1M | 0.23 s · 460 MB | 0.15 s · 356 MB | 0.12 s · 425 MB | 0.10 s · 196 MB |
| 10M | 3.31 s · 2,435 MB | 1.31 s · 1,339 MB | 0.99 s · 1,334 MB | **0.18 s · 428 MB** |
| 50M | sin memoria (OOM) | 7.91 s · 3,972 MB | 4.64 s · 4,633 MB | **0.74 s · 1,114 MB** |
| 50M con `-m 2g` | OOM | OOM | OOM | **0.75 s · 909 MB** |

Que pandas se quede sin memoria **es parte de la demo**, no un error: `pandas_naive` carga
todas las columnas y filas y las copia en el `merge` antes de filtrar. Para verlo rápido en
clase alcanza con 10M y `-m 2g` (abajo): ahí solo cae `pandas_naive`.

**Límite de memoria con Docker** (la forma más visual de mostrar el punto anterior):

```bash
docker run --rm -m 2g --memory-swap 2g -v "$PWD/data:/app/data" -v "$PWD/results:/app/results" \
  duckdb-vs-pandas python benchmark.py --rows 10_000_000 --repeat 1
```

`--memory-swap` igual a `-m` desactiva el swap: lo que no entra en 2 GB muere por falta de
memoria y el benchmark lo marca como `falló`. En Docker Desktop el tope real es la memoria
asignada a la VM (Settings → Resources).

## Qué mirar

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
un solo hilo y copias intermedias. Buen momento para medirlo en vez de creerlo.

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
