# Todo corre en contenedor: no hace falta Python, venv ni pip en tu máquina.
# uv instala las dependencias dentro de la imagen (rápido y reproducible).
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app
COPY requirements.txt .
RUN uv pip install --system --no-cache -r requirements.txt

COPY . .

# Por defecto corre el benchmark; los datos y los reportes viven en volúmenes montados.
CMD ["python", "benchmark.py", "--rows", "10000000", "--repeat", "3"]
