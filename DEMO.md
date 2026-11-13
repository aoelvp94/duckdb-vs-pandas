# Guion de demo (15-20 min): DuckDB vs pandas

Objetivo: que los alumnos *vean* que el mismo resultado se puede obtener con mucho menos
código manual, menos RAM y menos tiempo, y entiendan por qué.

## Antes de la clase (10 min, una sola vez)

```bash
docker build -t duckdb-vs-pandas .
alias dvp='docker run --rm -v "$PWD/data:/app/data" -v "$PWD/results:/app/results" duckdb-vs-pandas'
dvp python generate_data.py --rows 10_000_000
dvp python benchmark.py --rows 10_000_000 --repeat 3     # ensayo: llena el caché y valida todo
```

Solo hace falta Docker. El `alias dvp` hay que definirlo en cada terminal nueva.

- Tené el resultado del ensayo en `results/` por si la demo en vivo se demora.
- Cerrá apps que consuman RAM: los números salen más limpios.
- Terminal con fuente grande; dos paneles si podés (código a la izquierda, terminal a la derecha).

## Paso a paso

### 1. Plantear el problema (2 min)
Mostrá el pipeline en una frase: *"órdenes completadas desde 2023, con el país del cliente,
revenue mensual por país"*. Pedí a la clase que predigan: ¿cuál será más rápido y por qué?

### 2. Mostrar los tres códigos lado a lado (4 min)
Abrí `pipelines/pandas_naive.py`, `pipelines/pandas_pyarrow.py` y `pipelines/duckdb_sql.py`.
Puntos a marcar:
- En `pandas_naive` **el orden de tus líneas es el plan de ejecución**: join antes de filtrar.
- En `pandas_pyarrow` aparecen a mano el filtro en la lectura, la lista de columnas y el join.
- En `duckdb_sql` es una query de ~12 líneas y nada de eso está escrito.

### 3. Correr el benchmark (3 min)
```bash
dvp python benchmark.py --rows 10_000_000 --repeat 3
```
Mientras corre, hablá del método (ver `BENCHMARK.md`): proceso aislado, resultados verificados
idénticos, hay un pandas optimizado para que la comparación sea justa.
Mostrá la tabla y preguntá: ¿cuánto del speedup es *no leer lo que no usás* y cuánto es
paralelismo? (Pista: `pandas_pyarrow` ya tiene lo primero.)

### 4. Mirar el plan de DuckDB (3 min)
```bash
dvp python demo_duckdb_extras.py explain --rows 10_000_000
```
Buscá en el plan el filtro y la lista de columnas **dentro del scan de Parquet**.
Es el pushdown que en pandas escribiste a mano.

### 5. Datos más grandes que la memoria (3 min)
```bash
dvp python demo_duckdb_extras.py spill --rows 10_000_000 --memory 500MB
```
DuckDB trabaja con un límite de memoria bajo derramando a disco. Después probá escalar el
benchmark (`--rows 50_000_000`, si tu máquina aguanta) y mostrá cómo `pandas_naive` empieza
a fallar primero. Para forzarlo a propósito, limitá el contenedor:
```bash
docker run --rm -m 2g --memory-swap 2g -v "$PWD/data:/app/data" -v "$PWD/results:/app/results" \
  duckdb-vs-pandas python benchmark.py --rows 10_000_000 --repeat 1
```

### 6. Cierre: cuándo usar qué (2 min)
| Situación | Herramienta |
|---|---|
| Explorar datos chicos de forma interactiva | pandas |
| Agregaciones y joins sobre archivos grandes, sin servidor | DuckDB |
| Transformaciones versionadas, testeadas y orquestadas | dbt + DuckDB (ver el segundo repo) |

## Si algo sale mal en vivo
- `pandas_naive` mata el proceso por falta de memoria: es parte de la demo, el benchmark lo
  marca como `falló` y sigue.
- Los tiempos varían entre máquinas: usá el reporte del ensayo en `results/`.
- `dvp: command not found`: definí de nuevo el `alias dvp` en esa terminal.
- No encuentra los datos: corré `dvp python generate_data.py ...` desde la carpeta del repo.

## Preguntas para dejar a los alumnos
1. Reescribí `pandas_pyarrow` usando `Table.group_by().aggregate()` y sin pandas. ¿Cambia la RAM?
2. Agregá un filtro por `country`. ¿Qué engine se beneficia más y por qué?
3. Probá `SET threads=1` en DuckDB. ¿Cuánto del speedup era paralelismo?
