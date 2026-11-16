# Guía para alumnos: DuckDB vs pandas

En esta guía vas a instalar lo necesario, correr el mismo pipeline (filtro → join → revenue
mensual por país) con cuatro motores y comparar **tiempo** y **memoria**. Todo corre dentro de
Docker: no instalás Python, ni venv, ni paquetes en tu máquina.

| Paso | Tiempo aprox. |
|---|---|
| 1. Instalar Docker | 15-30 min (una sola vez) |
| 2. Chequear la instalación | 2 min |
| 3. Clonar y construir la imagen | 5-15 min la primera vez (depende de tu internet) |
| 4. Correr el benchmark | 5 min |
| 5. Probar los límites | 5 min |

> Hacé los pasos 1 a 3 **antes de la clase**: necesitan internet y la primera vez tardan.

---

## 1. Instalar Docker

Elegí tu sistema operativo.

### macOS

1. Instalá [Docker Desktop para Mac](https://docs.docker.com/desktop/setup/install/mac-install/)
   (elegí *Apple Silicon* si tu Mac tiene chip M1/M2/M3/M4, o *Intel* si no).
2. Abrilo y esperá a que diga *Engine running*.
3. Memoria: **Settings → Resources** y subí **Memory a 4 GB o más** (8 GB si podés). Apply & restart.

### Linux (Ubuntu, Debian, Fedora...)

1. Instalá [Docker Engine](https://docs.docker.com/engine/install/) siguiendo la guía de tu
   distribución.
2. Para usar `docker` sin `sudo`:
   ```bash
   sudo usermod -aG docker $USER
   ```
   Cerrá la sesión y volvé a entrar para que tome el cambio.
3. Memoria: en Linux Docker usa directamente la RAM de tu máquina, no hay nada que configurar.

### Windows

En Windows se trabaja dentro de **WSL2** (un Linux que corre dentro de Windows). Los comandos de
esta guía son de bash y **no funcionan en PowerShell ni en cmd**.

1. Instalá WSL2 con Ubuntu. En **PowerShell como administrador**:
   ```powershell
   wsl --install
   ```
   Reiniciá cuando te lo pida y creá tu usuario de Ubuntu.
   Más info: [instalar WSL](https://learn.microsoft.com/windows/wsl/install).
2. Instalá [Docker Desktop para Windows](https://docs.docker.com/desktop/setup/install/windows-install/)
   con la opción **Use WSL 2 based engine**.
3. En Docker Desktop: **Settings → Resources → WSL integration** y activá tu distro (Ubuntu).
4. Memoria: con WSL2 la memoria de Docker la define WSL, no Docker Desktop. Si tu máquina tiene
   poca RAM libre, creá el archivo `C:\Users\<tu-usuario>\.wslconfig` con:
   ```ini
   [wsl2]
   memory=8GB
   ```
   y en PowerShell corré `wsl --shutdown` para que lo tome.
5. **De acá en adelante, todo se hace en la terminal de Ubuntu** (buscá "Ubuntu" en el menú
   Inicio), y el repo se clona dentro de Ubuntu (`~/...`), **no** en `/mnt/c/...`, que es mucho
   más lento.

---

## 2. Chequear la instalación

En tu terminal (en Windows, la de Ubuntu):

```bash
docker run --rm hello-world
```

Tiene que imprimir *Hello from Docker!*. Después mirá cuánta memoria ve Docker:

```bash
docker info --format '{{.NCPU}} CPUs, {{.MemTotal}} bytes de RAM'
```

Con 4 GB (unos 4000000000 bytes) o más alcanza para esta guía.

---

## 3. Clonar y construir la imagen

```bash
git clone https://github.com/aoelvp94/duckdb-vs-pandas.git
cd duckdb-vs-pandas
docker build -t duckdb-vs-pandas .
```

La primera vez `docker build` baja la imagen base, DuckDB, pandas y PyArrow: con internet lenta
puede tardar más de 10 minutos. Las siguientes veces usa el caché y tarda segundos.

Definí un atajo para no escribir el `docker run` completo cada vez:

```bash
alias dvp='docker run --rm -v "$PWD/data:/app/data" -v "$PWD/results:/app/results" duckdb-vs-pandas'
```

El alias dura lo que dura la terminal: si abrís una nueva, definilo de nuevo. Corré todo desde la
carpeta del repo (`$PWD` tiene que ser `duckdb-vs-pandas`).

---

## 4. Correr el benchmark

### Generar datos

```bash
dvp python generate_data.py --rows 1_000_000
```

Crea `data/orders_1000000.parquet` (unos 20 MB) y `data/customers.parquet`.

### Comparar los cuatro motores

```bash
dvp python benchmark.py --rows 1_000_000 --repeat 3
```

Cada motor corre 3 veces en un proceso nuevo y se toma la mediana. Al final imprime una tabla así
(tus números van a ser otros):

```
engine            tiempo (s)   pico RAM (MB)   speedup
pandas_naive            0.23             460      1.0x
pandas_tuned            0.15             356      1.5x
pandas_pyarrow          0.12             425      1.9x
duckdb_sql              0.10             196      2.3x
```

El mismo reporte, con tu máquina y las versiones, queda en `results/benchmark_1000000.md`:

```bash
cat results/benchmark_1000000.md
```

Antes de comparar tiempos, el benchmark **verifica que los cuatro motores den exactamente el
mismo resultado**. Si alguno diera distinto, falla.

### Escalar a 10 millones de filas

```bash
dvp python generate_data.py --rows 10_000_000
dvp python benchmark.py --rows 10_000_000 --repeat 3
```

Con 1M las diferencias son chicas. Con 10M (unos 200 MB de Parquet) se separan mucho: compará tu
tabla con la de [BENCHMARK.md](BENCHMARK.md#resultados).

---

## 5. Probar los límites

### Sin memoria: pandas se cae, DuckDB sigue

Este comando corre el benchmark con el contenedor limitado a 2 GB:

```bash
docker run --rm -m 2g --memory-swap 2g -v "$PWD/data:/app/data" -v "$PWD/results:/app/results" \
  duckdb-vs-pandas python benchmark.py --rows 10_000_000 --repeat 1
```

Vas a ver `pandas_naive` marcado como **falló (exit -9)**: el sistema lo mató por falta de memoria.
**Es lo esperado**, no un error tuyo: `pandas_naive` carga todas las columnas y filas en RAM y las
copia en el `merge` antes de filtrar. Los otros tres leen solo lo que necesitan y terminan.
Este reporte se guarda aparte, en `results/benchmark_10000000_mem2g.md`.

### El plan de DuckDB

```bash
dvp python demo_duckdb_extras.py explain --rows 10_000_000
```

Buscá el bloque **Read Parquet**: ahí aparecen las columnas que lee (*Projections*) y el filtro
aplicado durante la lectura (*Filters*). Es lo que en pandas hay que escribir a mano.

### DuckDB con poca memoria

```bash
dvp python demo_duckdb_extras.py spill --rows 10_000_000 --memory 500MB
```

DuckDB termina igual con un límite de 500 MB: si le falta memoria, usa el disco.

---

## 6. Limpiar

Los datos generados ocupan espacio (10M filas son unos 200 MB). Para borrarlos:

```bash
rm -f data/*.parquet && rm -rf results
```

En **Linux**, esos archivos los creó el contenedor como root, así que hace falta `sudo`:

```bash
sudo rm -f data/*.parquet && sudo rm -rf results
```

Para borrar también la imagen de Docker: `docker rmi duckdb-vs-pandas`.

---

## Si algo falla

| Síntoma | Qué hacer |
|---|---|
| `dvp: command not found` | Definí de nuevo el `alias dvp` (paso 3) en esa terminal. |
| `Falta .../orders_10000000.parquet` | Generá primero los datos con ese mismo `--rows`. |
| `Cannot connect to the Docker daemon` | Docker no está corriendo: abrí Docker Desktop (Mac/Windows) o `sudo systemctl start docker` (Linux). |
| `permission denied` al usar `docker` en Linux | Te faltó el paso del grupo `docker` (sección 1, Linux) o cerrar y volver a entrar. |
| `docker build` falla o se corta | Suele ser la conexión: volvé a correrlo. La imagen base ya queda en caché; las dependencias se bajan de nuevo. |
| En Windows, todo anda muy lento | Clonaste el repo en `/mnt/c/...`: clonalo dentro de Ubuntu (`cd ~`). |

Más detalle del método y de los resultados: [BENCHMARK.md](BENCHMARK.md). El repo
[airflow-duckdb-dbt-demo](https://github.com/aoelvp94/airflow-duckdb-dbt-demo) lleva este mismo
pipeline a Airflow con dbt.
