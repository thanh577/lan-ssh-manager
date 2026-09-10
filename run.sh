#!/bin/bash
# Run LAN SSH Manager (single-port: backend + static frontend)
set -e
cd "$(dirname "$0")"
[ -f .env ] || cp .env.example .env
if [ ! -x backend/venv/bin/python ]; then
  python3 -m venv backend/venv
fi
backend/venv/bin/pip install -q -r backend/requirements.txt
mkdir -p data logs
echo "==> Open http://$(hostname -I 2>/dev/null | awk '{print $1}' || echo localhost):8000  (admin/admin123, đổi trong .env lần đầu)"
backend/venv/bin/python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
