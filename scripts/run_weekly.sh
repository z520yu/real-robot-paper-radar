#!/usr/bin/env bash
set -euo pipefail

ROOT="/home/b5090/embodied-paper-radar"
LOG_DIR="$ROOT/logs"
STAMP="$(date +%F)"

mkdir -p "$LOG_DIR"

cd "$ROOT"
python3 radar.py --config config/example_config.toml weekly >> "$LOG_DIR/weekly-$STAMP.log" 2>&1
