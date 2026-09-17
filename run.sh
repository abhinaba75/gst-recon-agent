#!/bin/sh
# Recon-Agent preview launcher.
# Binds 0.0.0.0 and honours the injected PORT (defaults to 8501 locally).
#
# DEMO-ONLY: CORS and XSRF protection are disabled so Streamlit's WebSocket
# accepts the reverse-proxied preview origin. Combined with 0.0.0.0 this lets
# anyone on the network POST to the app — never copy these flags into a
# production or shared deployment.
PORT="${PORT:-8501}"
cd "$(dirname "$0")"
exec .venv/bin/streamlit run frontend/app.py \
  --server.port "$PORT" \
  --server.address 0.0.0.0 \
  --server.headless true \
  --server.enableCORS false \
  --server.enableXsrfProtection false
