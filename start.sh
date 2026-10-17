#!/bin/sh
set -eu
cd "$(dirname "$0")"
python3 scripts/setup.py
docker compose config --quiet
docker compose up -d
python3 scripts/check-network.py
