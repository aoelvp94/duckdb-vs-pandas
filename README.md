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
todas las columnas y filas y las copia en el `merge` antes de filtrar. Para verlo rápido
alcanza con 10M y `-m 2g` (abajo): ahí solo cae `pandas_naive`.

### ¿Por qué DuckDB es más rápido y usa menos memoria?

Los cuatro motores hacen exactamente lo mismo y dan el mismo resultado (el benchmark lo verifica).
La diferencia está en **cuánto leen, en qué orden trabajan y cuánto tienen en memoria a la vez**.

1. **Lee menos.** `pandas_naive` carga las 9 columnas y todas las filas. DuckDB lee solo las 5
   que usa la query y aplica el filtro **mientras lee** el Parquet: lo ves en
   `dvp python demo_duckdb_extras.py explain`, en el bloque *Read Parquet* (*Projections* y
   *Filters*). `notes` y `channel` nunca llegan a memoria.
2. **Filtra antes del join.** `pandas_naive` hace el `merge` con las 10M filas y recién después
   filtra. Del filtro sobreviven 3,999,662 filas (un 40 %): el 60 % del join fue trabajo tirado.
   DuckDB reordena solo filtro y join; en pandas, el orden de tus líneas *es* el plan.
3. **Usa todos los cores.** DuckDB reparte el trabajo entre los 10 CPUs. En pandas, el `merge` y
   el `groupby` corren en un solo hilo (la lectura de Parquet sí usa varios, vía PyArrow).
4. **No necesita la tabla entera en memoria.** DuckDB procesa los datos por partes, en streaming.
   Por eso a 50M filas con un límite de 2 GB termina en 0.75 s usando 909 MB, mientras los tres
   pandas se quedan sin memoria: pandas materializa cada paso como un DataFrame completo.

**¿Y los pandas optimizados?** `pandas_tuned` y `pandas_pyarrow` hacen a mano lo que DuckDB hace
solo (leer menos columnas, filtrar en la lectura) y eso los acerca: a 10M bajan de 3.31 s a
1.31 s y 0.99 s. Pero igual guardan en memoria todas las filas que pasan el filtro, así que a 50M
necesitan 4 GB o más y con 2 GB también caen. Más rápido tampoco es siempre menos RAM: a 50M
PyArrow usa más que tuned (4,633 contra 3,972 MB).

**¿Por qué a 1M casi no hay diferencia?** Porque todo entra cómodo en memoria y hay poco trabajo:
0.10 s contra 0.12-0.23 s. Además, el pico de RAM incluye a Python y a las librerías, un piso
fijo para todos. Las diferencias aparecen al crecer los datos.

**Un detalle que pesa**: formatear el mes con `strftime` fila por fila era el 70 % del tiempo de
`pandas_pyarrow` a 10M. Ahora agrupa por el mes truncado y formatea solo las ~240 filas del
resultado. DuckDB no necesita ese truco: el optimizador lo resuelve. Optimizar pandas a mano
exige saber dónde está el costo.

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

## Para seguir explorando

Ideas para profundizar por tu cuenta. En cada una, antes de correr, anotá **qué esperás** que
pase con el tiempo y la RAM, y después compará con lo que medís.

**Medir mejor**

1. **Encontrá el límite de cada motor.** Con `-m 2g`, probá 10M, 20M y 30M filas. ¿A partir de
   cuántas filas caen `pandas_tuned` y `pandas_pyarrow`? Repetí con `-m 4g`.
2. **¿Cuánto le debe DuckDB al paralelismo?** Corré el benchmark con `--cpus 1` en el
   `docker run`. ¿Cuánto se acerca pandas? ¿Qué motor cambia más?
3. **Variación.** Corré `--repeat 5` dos veces seguidas con 10M. ¿Cuánto cambia la mediana entre
   corridas? ¿Qué diferencias de la tabla podés considerar reales?

**Otros motores**

4. **Polars.** Agregá `pipelines/polars_lazy.py` con el mismo pipeline usando `polars`
   (motor en Rust, lazy, con pushdown en `scan_parquet`), sumalo a `ENGINES` en `benchmark.py` y a
   `requirements.txt`, y reconstruí la imagen. El benchmark verifica solo que dé lo mismo.
5. **Cero pandas.** Reescribí `pandas_pyarrow` usando `pyarrow.Table.group_by(...).aggregate(...)`
   en lugar del `groupby` de pandas. ¿Cambia el tiempo o la RAM?
6. **SQL sobre un DataFrame.** DuckDB puede consultar un DataFrame de pandas que ya está en
   memoria (`duckdb.sql("select ... from df")`). Cargá los datos con pandas y hacé la agregación
   con DuckDB: ¿qué parte del costo desaparece y cuál no?

**Entender DuckDB**

7. Cambiá `explain` por `EXPLAIN ANALYZE` en `demo_duckdb_extras.py`: ¿en qué operador se va el
   tiempo?
8. Corré `dvp python demo_duckdb_extras.py spill --rows 50_000_000 --memory 500MB`. ¿Termina?
   ¿Cuánto más tarda que sin límite?
9. Reescribí `pandas_tuned` hasta alcanzar a DuckDB. ¿Cuánto código manual hizo falta?

**Llevarlo a tu proyecto**

10. Tomá una transformación de tu proyecto final escrita en pandas y reescribila en SQL. Comparala
    en tiempo, en líneas de código y en qué tan fácil es leerla. Ese SQL es lo que después
    organiza dbt: mirá el repo
    [airflow-duckdb-dbt-demo](https://github.com/aoelvp94/airflow-duckdb-dbt-demo).

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
