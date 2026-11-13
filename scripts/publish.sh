#!/usr/bin/env bash
# Publica este repo en tu cuenta de GitHub. Requiere: git y gh (gh auth login).
set -euo pipefail
cd "$(dirname "$0")/.."

NAME="duckdb-vs-pandas"
DESC="Mismo pipeline en pandas vs DuckDB: benchmark de tiempo y RAM (Le Wagon)"

[ -d .git ] || git init -b main
git add .
git commit -m "feat: DuckDB vs pandas benchmark MWE" || true
gh repo create "$NAME" --public --source=. --push --description "$DESC"
gh repo edit --add-topic duckdb --add-topic pandas --add-topic benchmark --add-topic data-engineering
echo "Listo: $(gh repo view --json url -q .url)"
