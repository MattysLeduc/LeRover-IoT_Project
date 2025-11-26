#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../src/telemetry"
exec python3 telemetry_runner.py
