#!/usr/bin/env bash
# Reproducible lab reset: wipes and re-seeds lab-db, restarts the lab
# containers. Run from the repo root: ./lab/scripts/reset.sh
set -euo pipefail

echo "Resetting AEGIS Labs..."
docker compose stop lab-api lab-internal-mock
docker compose rm -f lab-api lab-internal-mock

python3 -m pip install -q asyncpg
LAB_DATABASE_URL="${LAB_DATABASE_URL:-postgresql://lab:lab_dev_only@localhost:5433/aegis_lab}" \
  python3 lab/scripts/seed.py

docker compose up -d lab-db lab-internal-mock lab-api
echo "Lab reset complete."
