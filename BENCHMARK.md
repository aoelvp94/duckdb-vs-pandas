# Benchmark: qué mide, cómo y cómo leerlo

## El pipeline

Un caso típico de analítica sobre e-commerce, idéntico en los cuatro engines:

1. Leer `orders` (N filas, 9 columnas) y `customers` (500 mil filas) desde Parquet.
2. Quedarse con las órdenes `completed` desde `2023-01-01`.
3. Join con `customers` para traer el país.
4. Calcular `net = quantity * unit_price * (1 - discount)`.
5. Agrupar por país y mes: cantidad de órdenes, revenue y ticket promedio.

## Los cuatro engines (la escalera de optimización)

| Engine | Qué hace | Qué sigue siendo manual |
|---|---|---|
| `pandas_naive` | Lee todas las columnas y filas, join antes de filtrar | Todo |
| `pandas_tuned` | Lee solo las columnas necesarias y filtra en la lectura (`columns=`, `filters=`) | Elegir columnas, escribir el filtro |
| `pandas_pyarrow` | `pyarrow.dataset` con pushdown, join en Arrow (multihilo), `ArrowDtype` | Lo anterior más ordenar los pasos |
| `duckdb_sql` | Una query SQL; el optimizador hace pushdown, join y paralelismo | Solo escribir el SQL |

## Cómo se mide

- **Un proceso nuevo por corrida** (`run_one.py`): sin caché de imports ni memoria heredada.
- **Tiempo**: `perf_counter` alrededor de la ejecución completa del pipeline (lectura incluida), mediana de `--repeat` corridas.
- **Pico de RAM**: `ru_maxrss` del proceso (el máximo entre corridas). Incluye el intérprete y las librerías, así que hay un piso de decenas de MB para todos.
- **Resultados verificados**: el benchmark falla si algún engine devuelve algo distinto (tolerancia `1e-6` relativa en los flotantes). Comparar velocidad de pipelines que dan resultados distintos no tiene sentido.
- **Si un engine se queda sin memoria**, queda marcado como `falló` en la tabla.

## Cómo correrlo

```bash
docker build -t duckdb-vs-pandas .
alias dvp='docker run --rm -v "$PWD/data:/app/data" -v "$PWD/results:/app/results" duckdb-vs-pandas'

dvp python generate_data.py --rows 10_000_000
dvp python benchmark.py --rows 10_000_000 --repeat 3
```

Cada corrida guarda `results/benchmark_<rows>.md` con la máquina, las versiones y la tabla
(con límite de memoria, `results/benchmark_<rows>_mem2g.md`, para no pisar el anterior).
Probá escalas distintas (`1_000_000`, `10_000_000`, `50_000_000`) y pegá abajo los resultados.

## Resultados

Medido el 13-nov-2026. Los números dependen del hardware, de los recursos asignados a Docker
y de las versiones: usalos como referencia y medí en tu máquina.

**Entorno**

- Host: Apple M4, 24 GB de RAM, macOS 26.5.2.
- Docker Desktop (engine 29.9.2) con **10 CPUs y 7.7 GiB** asignados a la VM
  (Settings → Resources). Eso es lo que ve el contenedor, no la RAM del host.
- Imagen de este repo (`docker build -t duckdb-vs-pandas .`): Python 3.12.12, DuckDB 2.0.0,
  pandas 3.1.1, PyArrow 26.0.1, NumPy 2.5.4.
- 1M y 10M: sin otros contenedores corriendo. 50M y las corridas con límite de memoria: había
  otro proyecto de Airflow ocioso en la misma VM (6-11 % de CPU, ~2 GiB de RAM).

### 1,000,000 filas (`orders` = 20 MB en Parquet)

- Máquina: Linux 7.0.14-linuxkit (aarch64), 10 CPUs, 7.7 GiB RAM
- Versiones: Python 3.12.12, DuckDB 2.0.0, pandas 3.1.1, PyArrow 26.0.1
- Método: mediana de 3 corridas, cada una en un proceso nuevo; resultados verificados idénticos entre engines

| Engine | Tiempo (s) | Pico RAM (MB) | Speedup vs naive |
|---|---:|---:|---:|
| pandas naive (lee todo, join antes de filtrar) | 0.23 | 460 | 1.0x |
| pandas tuned (columnas + filtros en la lectura) | 0.15 | 356 | 1.5x |
| pandas + PyArrow (pushdown y join en Arrow) | 0.12 | 425 | 1.9x |
| DuckDB (SQL) | 0.10 | 196 | 2.3x |

### 10,000,000 filas (`orders` = 201 MB en Parquet)

- Máquina: Linux 7.0.14-linuxkit (aarch64), 10 CPUs, 7.7 GiB RAM
- Versiones: Python 3.12.12, DuckDB 2.0.0, pandas 3.1.1, PyArrow 26.0.1
- Método: mediana de 3 corridas, cada una en un proceso nuevo; resultados verificados idénticos entre engines

| Engine | Tiempo (s) | Pico RAM (MB) | Speedup vs naive |
|---|---:|---:|---:|
| pandas naive (lee todo, join antes de filtrar) | 3.31 | 2,435 | 1.0x |
| pandas tuned (columnas + filtros en la lectura) | 1.31 | 1,339 | 2.5x |
| pandas + PyArrow (pushdown y join en Arrow) | 0.99 | 1,334 | 3.3x |
| DuckDB (SQL) | 0.18 | 428 | 18.4x |

### 50,000,000 filas (`orders` = 1003 MB en Parquet)

- Máquina: Linux 7.0.14-linuxkit (aarch64), 10 CPUs, 7.7 GiB RAM
- Versiones: Python 3.12.12, DuckDB 2.0.0, pandas 3.1.1, PyArrow 26.0.1
- Método: mediana de 3 corridas, cada una en un proceso nuevo; resultados verificados idénticos entre engines

| Engine | Tiempo (s) | Pico RAM (MB) | Speedup vs naive |
|---|---:|---:|---:|
| pandas naive (lee todo, join antes de filtrar) | falló | falló | - |
| pandas tuned (columnas + filtros en la lectura) | 7.91 | 3,972 | - |
| pandas + PyArrow (pushdown y join en Arrow) | 4.64 | 4,633 | - |
| DuckDB (SQL) | 0.74 | 1,114 | - |

`pandas_naive` muere por falta de memoria (exit -9, OOM-killer) en las 3 corridas, y **es lo
esperado**: carga las 9 columnas y todas las filas, y el `merge` las copia antes de filtrar.
A 10M ya pide 2.4 GB; a 50M no entra en los 7.7 GiB de la VM. Los otros tres leen solo lo que
necesitan y terminan.

### Con límite de memoria: `docker run -m 2g --memory-swap 2g`

10M filas (`--repeat 1`):

- Máquina: Linux 7.0.14-linuxkit (aarch64), 10 CPUs, 7.7 GiB RAM, límite del contenedor 2 GiB
- Versiones: Python 3.12.12, DuckDB 2.0.0, pandas 3.1.1, PyArrow 26.0.1
- Método: mediana de 1 corridas, cada una en un proceso nuevo; resultados verificados idénticos entre engines

| Engine | Tiempo (s) | Pico RAM (MB) | Speedup vs naive |
|---|---:|---:|---:|
| pandas naive (lee todo, join antes de filtrar) | falló | falló | - |
| pandas tuned (columnas + filtros en la lectura) | 1.01 | 1,355 | - |
| pandas + PyArrow (pushdown y join en Arrow) | 0.55 | 1,330 | - |
| DuckDB (SQL) | 0.20 | 427 | - |

50M filas (`--repeat 1`):

- Máquina: Linux 7.0.14-linuxkit (aarch64), 10 CPUs, 7.7 GiB RAM, límite del contenedor 2 GiB
- Versiones: Python 3.12.12, DuckDB 2.0.0, pandas 3.1.1, PyArrow 26.0.1
- Método: mediana de 1 corridas, cada una en un proceso nuevo; terminó un solo engine: sin verificación cruzada

| Engine | Tiempo (s) | Pico RAM (MB) | Speedup vs naive |
|---|---:|---:|---:|
| pandas naive (lee todo, join antes de filtrar) | falló | falló | - |
| pandas tuned (columnas + filtros en la lectura) | falló | falló | - |
| pandas + PyArrow (pushdown y join en Arrow) | falló | falló | - |
| DuckDB (SQL) | 0.75 | 909 | - |

Con 2 GiB, a 10M solo cae `pandas_naive` (es la demo más rápida para clase). A 50M caen los tres
pandas y DuckDB termina en menos de un segundo usando menos de 1 GB: procesa en streaming y no
necesita tener la tabla entera en memoria.

**Variación entre corridas**: en otras corridas de 10M sobre la misma máquina, `pandas_tuned`
dio entre 1.0 y 1.9 s y `pandas_pyarrow` entre 0.55 y 1.0 s. El orden de los engines no cambió.
Por eso la tabla usa la mediana; las diferencias de menos de ~2x entre los pandas no son
significativas con 3 corridas.

## Cómo leer los resultados

- **Tiempo**: DuckDB suele ganar por tres razones combinadas: ejecución columnar y vectorizada,
  paralelismo en todos los cores por defecto y que lee solo lo que necesita. pandas ejecuta
  cada operación en un hilo y materializa cada paso intermedio.
- **RAM**: `pandas_naive` carga todas las columnas y filas y además copia en el `merge`.
  Las columnas que el pipeline no usa (`notes`, `channel`) son justamente el costo oculto.
- **Un detalle que pesa mucho**: formatear el mes con `strftime` fila por fila es lento
  (en Arrow, 1.6 s sobre 4M filas a 10M, el 70 % de `pandas_pyarrow`). Por eso ese pipeline agrupa por
  el mes truncado (`pc.floor_temporal`) y formatea `"YYYY-MM"` sobre las ~240 filas del resultado.
  DuckDB no necesita ese truco: el optimizador lo resuelve.
- **`pandas_tuned` y `pandas_pyarrow` no son hombres de paja**: son lo que un buen ingeniero
  escribiría a mano. La conclusión no es "pandas es malo" sino cuánto trabajo manual
  reemplaza un optimizador de queries.
- **pandas 3**: las columnas de texto usan un dtype `str` respaldado por PyArrow, así que la
  brecha de memoria en strings es menor que con pandas 2. Lo estructural (un solo hilo,
  copias intermedias, leer de más) no cambia.

## Limitaciones (decirlas en voz alta)

- **Una sola query**, de tipo agregación sobre un dataset que cabe en disco. En exploración
  interactiva, datos chicos o transformaciones fila a fila, pandas sigue siendo excelente.
- **Datos sintéticos**: la distribución (uniforme, pocas cardinalidades) favorece a los engines
  columnares. Con datos reales los números cambian.
- **Caché de disco**: la primera corrida lee del disco y las siguientes del caché del sistema.
  Por eso se usa la mediana y `--repeat 3` o más.
- **La RAM no es el límite de DuckDB**: con `memory_limit` baja puede derramar a disco
  (`dvp python demo_duckdb_extras.py spill`). Eso no está en la tabla porque cambia lo que se mide.
- **Una máquina, un sistema operativo**: no extrapolar a clusters ni a otro hardware.
- **Docker agrega una capa**: en Mac y Windows el contenedor corre dentro de una VM, así que los
  CPUs y la RAM disponibles son los asignados a Docker Desktop, no los de tu máquina. Anotalos junto
  a los resultados; el reporte de `benchmark.py` los muestra desde dentro del contenedor.
