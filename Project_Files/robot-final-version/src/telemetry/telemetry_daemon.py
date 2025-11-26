#!/usr/bin/env python3
import os, sys, json, time, csv, signal, base64
from pathlib import Path
from datetime import datetime, timezone
from dateutil import tz
import paho.mqtt.client as mqtt

BASE = Path(__file__).resolve().parent.parent   # repo/
CFG_DIR = BASE / "config"

# --------- config helpers ----------
def load_json_candidates(name, fallbacks=()):
    """Load JSON from config/name, else try fallbacks (paths)."""
    cands = [CFG_DIR / name, *[Path(p) for p in fallbacks]]
    for p in cands:
        try:
            if p.exists():
                return json.loads(p.read_text())
        except Exception as e:
            print(f"[cfg] failed to read {p}: {e}", file=sys.stderr)
    return {}

def load_configs():
    # Primary: repo/config/*.json
    ada = load_json_candidates("adafruit.json", fallbacks=[
        # fallback to course code’s Server/adafruit.json if it exists
        BASE.parent / "adafruit.json"
    ])
    app = load_json_candidates("app.local.json")
    if not app:
        # fallback to sample defaults if user didn’t create local yet
        app = load_json_candidates("app.sample.json")
    # normalize structure (support nested {"adafruit":{...}})
    if "adafruit" in ada:
        ada = ada["adafruit"]
    return ada, app

# --------- cache readers (NO GPIO) ----------
IR_TRIP  = Path("/tmp/ir_triplet.txt")   # expected "L M R"
LINEFILE = Path("/tmp/line_state.txt")   # "LMR" or "NONE"
ULTRA    = Path("/tmp/ultra_cm.txt")     # float cm

def read_ir_triplet():
    try:
        if IR_TRIP.exists():
            parts = IR_TRIP.read_text().strip().replace(","," ").split()
            if len(parts) >= 3:
                L, M, R = (int(parts[0]), int(parts[1]), int(parts[2]))
                return max(0,min(1,L)), max(0,min(1,M)), max(0,min(1,R))
    except Exception:
        pass
    return None

def read_line_state():
    try:
        if LINEFILE.exists():
            s = LINEFILE.read_text().strip().upper()
            # normalize: "", "NONE" => "___"; else compact like "LM", "R", "LMR"
            if not s or s == "NONE":
                return "___"
            # ensure fixed-width indicator
            return f"{'L' if 'L' in s else '_'}{'M' if 'M' in s else '_'}{'R' if 'R' in s else '_'}"
    except Exception:
        pass
    return "___"

def read_ultra_cm(max_age_sec=1.5):
    try:
        if ULTRA.exists():
            # optionally ignore very stale values
            if (time.time() - ULTRA.stat().st_mtime) > max_age_sec:
                return None
            return float(ULTRA.read_text().strip())
    except Exception:
        pass
    return None

# --------- CSV with daily rotation ----------
class DailyCSV:
    def __init__(self, tzname="America/Toronto"):
        self.tz = tz.gettz(tzname) or tz.UTC
        self.curr_date = None
        self.f = None
        self.writer = None

    def _path_for(self, d: datetime):
        day = d.strftime("%Y-%m-%d")
        return BASE / "data" / f"{day}_robot_telemetry.csv"

    def _ensure_open(self, now: datetime):
        day = now.date()
        if self.curr_date != day:
            if self.f:
                try: self.f.close()
                except Exception: pass
            p = self._path_for(now)
            p.parent.mkdir(parents=True, exist_ok=True)
            newfile = not p.exists()
            self.f = open(p, "a", newline="")
            self.writer = csv.writer(self.f)
            if newfile:
                self.writer.writerow(["timestamp_iso", "ultrasonic_cm", "ir_left", "ir_center", "ir_right", "line_state"])
            self.curr_date = day

    def log(self, now: datetime, ultra, L, M, R, state):
        self._ensure_open(now)
        self.writer.writerow([now.isoformat(timespec="seconds"), "" if ultra is None else f"{ultra:.1f}", 
                              "" if L is None else L, "" if M is None else M, "" if R is None else R, state])
        try: self.f.flush()
        except Exception: pass

    def close(self):
        try:
            if self.f: self.f.close()
        except Exception:
            pass

# --------- MQTT publisher ----------
class AIOPublisher:
    def __init__(self, username, key, feeds, host="io.adafruit.com", port=1883):
        self.username = username
        self.key = key
        self.feeds = feeds
        self.host = host
        self.port = int(port)
        self.client = mqtt.Client(client_id="telemetry-daemon", clean_session=True)
        self.client.username_pw_set(username, key)
        self.client.reconnect_delay_set(min_delay=2, max_delay=30)
        self.client.loop_start()
        try:
            self.client.connect(self.host, self.port, keepalive=60)
        except Exception as e:
            print(f"[mqtt] initial connect error: {e}", file=sys.stderr)

    def topic(self, key):
        return f"{self.username}/feeds/{self.feeds[key]}"

    def pub(self, key, value, retain=False, qos=0):
        try:
            self.client.publish(self.topic(key), str(value), qos=qos, retain=retain)
        except Exception as e:
            print(f"[mqtt] publish error: {e}", file=sys.stderr)

    def close(self):
        try: self.client.loop_stop()
        except Exception: pass
        try: self.client.disconnect()
        except Exception: pass

# --------- main loop ----------
RUN = True
def _sig(sig, frame):
    global RUN
    RUN = False
signal.signal(signal.SIGINT, _sig)
signal.signal(signal.SIGTERM, _sig)

def main():
    ada, app = load_configs()
    if not ada or not ada.get("username") or not ada.get("key") or not ada.get("feeds"):
        print("[error] Missing Adafruit IO config. Copy config/adafruit.sample.json to config/adafruit.json and fill it.", file=sys.stderr)
        return 2

    # env override if present
    user = os.getenv("AIO_USERNAME", ada.get("username"))
    key  = os.getenv("AIO_KEY", ada.get("key"))
    feeds = ada["feeds"]
    host = ada.get("host", "io.adafruit.com")
    port = ada.get("port", 1883)

    tzname = app.get("timezone", "America/Toronto")
    csvlog = DailyCSV(tzname)

    # intervals (seconds)
    itv = app.get("intervals", {})
    dt_us = float(itv.get("ultrasonic_sec", 0.5))
    dt_ir = float(itv.get("infrared_sec", 0.2))
    dt_cam = float(itv.get("camera_sec", 5.0))  # we only publish status string here

    pub = AIOPublisher(user, key, feeds, host=host, port=port)

    t_us = t_ir = t_cam = 0.0
    print("[telemetry-daemon] running (cache-only). Ctrl+C to stop.")
    try:
        while RUN:
            now = time.time()
            now_local = datetime.now(tz=tz.gettz(tzname) or tz.UTC)

            # Ultrasonic (from cache writer)
            if now - t_us >= dt_us:
                t_us = now
                d = read_ultra_cm()
                if d is not None:
                    pub.pub("ultrasonic_cm", f"{d:.1f}")
                # include in CSV either way (None becomes blank)

            # Infrared + line state (from line_follow / cache-writer)
            L = M = R = None
            if now - t_ir >= dt_ir:
                t_ir = now
                ir = read_ir_triplet()
                state = read_line_state()
                if ir:
                    L, M, R = ir
                    pub.pub("ir_left",   L)
                    pub.pub("ir_center", M)
                    pub.pub("ir_right",  R)
                    pub.pub("line_state", state)
                else:
                    # still publish the state string (e.g., "___") if present
                    pub.pub("line_state", state)

                # Log row (1 Hz is fine; here we log on each IR tick)
                d = read_ultra_cm()
                csvlog.log(now_local, d, L, M, R, state)

            # Camera status heartbeat (we don't access camera here; car_tui owns it)
            if now - t_cam >= dt_cam:
                t_cam = now
                pub.pub("camera_status", "idle")  # cache-only daemon can't access camera

            time.sleep(0.02)
    finally:
        csvlog.close()
        pub.close()
        print("[telemetry-daemon] stopped.")

if __name__ == "__main__":
    sys.exit(main())
