#!/usr/bin/env python3
import json, os, sys, datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent
# Look for config in config/ directory (parent of src/)
CFG_PATH = BASE.parent.parent / "config" / "adafruit.json"
# Fallback to src/telemetry/ if not found
if not CFG_PATH.exists():
    CFG_PATH = BASE / "adafruit.json"

# Load your real runtime config (kept out of git)
cfg = json.load(open(CFG_PATH))

# Compute date-stamped CSV in repo/data/
today = datetime.datetime.utcnow().strftime("%Y-%m-%d")
data_dir = BASE.parent / "data"
data_dir.mkdir(parents=True, exist_ok=True)
csv_name = f"{today}_robot_telemetry.csv"
csv_path = data_dir / csv_name

# Ensure logging block exists and override path
cfg.setdefault("local_log", {})
cfg["local_log"]["enabled"] = True
cfg["local_log"]["path"] = str(csv_path.relative_to(BASE.parent))  # e.g., "data/2025-11-01_robot_telemetry.csv"

# Pass intervals through if not present
cfg.setdefault("intervals", {"ultrasonic_sec":0.5,"infrared_sec":0.2,"camera_sec":5.0})

# Write a temporary merged config the telemetry module will read
tmp_cfg = BASE / ".merged_adafruit.json"
with open(tmp_cfg, "w") as f:
    json.dump(cfg, f, indent=2)

# Monkey-patch telemetry to read our merged file (no edits to your original telemetry.py)
os.environ["AIO_CFG_OVERRIDE"] = str(tmp_cfg)

# Run telemetry main loop
if __name__ == "__main__":
    import importlib.util
    spec = importlib.util.spec_from_file_location("telemetry", str(BASE / "telemetry.py"))
    telem = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(telem)
    
    # Actually start the telemetry loop (since __name__ != "__main__" when imported)
    if hasattr(telem, "Telemetry"):
        print(f"[telemetry-runner] Starting telemetry with config: {CFG_PATH}")
        telem.Telemetry(cfg).loop()
    else:
        print("[telemetry-runner] Error: Telemetry class not found in telemetry.py", file=sys.stderr)
        sys.exit(1)
