#!/bin/bash
# Backup database + config (timestamped), never log secrets
set -e
cd "$(dirname "$0")/.."
TS=$(date +%Y%m%d_%H%M%S)
mkdir -p backup/database backup/config
cp data/lan_ssh_manager.db "backup/database/lan_ssh_manager_${TS}.db" 2>/dev/null || echo "No DB yet"
cp .env.example "backup/config/env_example_${TS}.txt" 2>/dev/null || true
echo "Backup done: backup/database/lan_ssh_manager_${TS}.db"
