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

Cada corrida guarda `results/benchmark_<rows>.md` con la máquina, las versiones y la tabla.
Probá escalas distintas (`1_000_000`, `10_000_000`, `50_000_000`) y pegá abajo los resultados.

## Resultados

> Todavía no hay números publicados en este repo. Corré el benchmark en tu máquina y pegá
> acá el contenido de `results/benchmark_<rows>.md`. Los resultados dependen del hardware
> (cantidad de cores, disco, RAM) y de las versiones, por eso el reporte las incluye.

<!-- Pegar abajo los reportes generados -->

## Cómo leer los resultados

- **Tiempo**: DuckDB suele ganar por tres razones combinadas: ejecución columnar y vectorizada,
  paralelismo en todos los cores por defecto y que lee solo lo que necesita. pandas ejecuta
  cada operación en un hilo y materializa cada paso intermedio.
- **RAM**: `pandas_naive` carga todas las columnas y filas y además copia en el `merge`.
  Las columnas que el pipeline no usa (`notes`, `channel`) son justamente el costo oculto.
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
