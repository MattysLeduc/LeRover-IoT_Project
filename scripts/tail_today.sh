#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
f="data/$(date -u +%F)_robot_telemetry.csv"
echo "Tailing $f (UTC dating) ..."
touch "$f"
tail -n +1 -f "$f"
