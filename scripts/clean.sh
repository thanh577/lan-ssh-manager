#!/bin/bash
# Clean only safe generated files. NEVER deletes data/, .env, database.
set -e
cd "$(dirname "$0")/.."
find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
find . -name "*.pyc" -delete 2>/dev/null || true
rm -rf frontend/dist backup/tmp 2>/dev/null || true
echo "Cleaned (data/ and .env kept)."
