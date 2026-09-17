#!/bin/sh
# Recon-Agent preview launcher.
# Binds 0.0.0.0 and honours the injected PORT (defaults to 8501 locally).
PORT="${PORT:-8501}"
cd "$(dirname "$0")"
exec .venv/bin/streamlit run frontend/app.py \
  --server.port "$PORT" \
  --server.address 0.0.0.0 \
  --server.headless true \
  --server.enableCORS false \
  --server.enableXsrfProtection false
