#!/bin/sh
# Recon-Agent web launcher — the FastAPI engine plus the Vite SPA.
#
# One command, one port: the SPA is served by Vite, which proxies /api to the
# Python engine on 127.0.0.1:8000. If the engine cannot start (no fastapi, no
# credentials, offline) the site still renders its exported snapshot and says
# plainly that no dispatch will be delivered.
set -e
cd "$(dirname "$0")"

if [ -x .venv/bin/python ]; then
  .venv/bin/python -m uvicorn api.main:app \
    --host 127.0.0.1 --port 8000 --log-level warning &
fi

cd web
exec bun run dev
