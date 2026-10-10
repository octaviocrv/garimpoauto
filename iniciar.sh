#!/usr/bin/env bash
# Sobe o servidor (porta 8000) e a tela (porta 5173) juntos. Ctrl+C derruba os dois.
# Uso: ./iniciar.sh
set -e
raiz="$(cd "$(dirname "$0")" && pwd)"

if [ ! -x "$raiz/scraper/.venv/bin/uvicorn" ]; then
  echo "Falta o ambiente Python em scraper/.venv (veja scraper/requirements.txt)." >&2; exit 1
fi
[ -d "$raiz/apps/web/node_modules" ] || (cd "$raiz/apps/web" && npm install)

trap 'kill 0' EXIT
(cd "$raiz/scraper" && .venv/bin/uvicorn server:app --port 8000) &
(cd "$raiz/apps/web" && npm run dev -- --host) &
wait
