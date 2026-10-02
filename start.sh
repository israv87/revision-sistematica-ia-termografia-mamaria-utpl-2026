#!/bin/sh
set -eu
exec python -m streamlit run brujula_bibliografica/app.py --server.address 0.0.0.0 --server.port "${PORT:-8501}" --server.headless true
