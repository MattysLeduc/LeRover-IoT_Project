#!/usr/bin/env python3
import os, json, time, base64, datetime, csv, ssl
from pathlib import Path
from typing import Optional
import paho.mqtt.client as mqtt

BASE = Path(__file__).resolve().parent

# Cache files written by car_tui.py and line_follow.py
IR_CACHE    = Path("/tmp/ir_lmr.txt")     # "L M R" as three ints
ULTRA_CACHE = Path("/tmp/ultra_cm.txt")   # "123.4"

# Optional OpenCV (non-GPIO)
cv2 = None
try:
    import cv2  # noqa
    cv2 = cv2
except Exception:
    pass

def now_iso(): return datetime.datetime.now().isoformat(timespec="seconds")

def load_cfg():
    cfg = json.loads((BASE/"adafruit.json").read_text())
    a = cfg["adafruit"] if "adafruit" in cfg else cfg
    username = a.get("username") or a.get("user")
    key      = a.get("key") or a.get("aio_key")
    feeds    = a["feeds"]
    host     = a.get("host", "io.adafruit.com")
    port     = int(a.get("port", 8883))   # default to TLS port
    itv = cfg.get("intervals", {})
    intervals = {
        # Safer defaults for AIO free-tier (≤ 30 msg/min total)
        "infrared_sec":  float(itv.get("infrared_sec", 2.0)),
        "ultrasonic_sec":float(itv.get("ultrasonic_sec",2.0)),
        "camera_sec":    float(itv.get("camera_sec",   10.0)),
    }
    log_cfg = cfg.get("local_log", {"enabled": True, "path": "logs/telemetry.csv"})
    return username, key, host, port, feeds, intervals, log_cfg

# ---------- Cache readers (NO GPIO) ----------
def read_ir_cached(max_age=2.5) -> Optional[tuple[int,int,int]]:
    try:
        if IR_CACHE.exists() and (time.time() - IR_CACHE.stat().st_mtime) <= max_age:
            txt = IR_CACHE.read_text().strip()
            parts = txt.replace(",", " ").split()
            if len(parts) >= 3:
                L, M, R = int(parts[0]), int(parts[1]), int(parts[2])
                return L, M, R
    except Exception:
        pass
    return None

def read_ultra_cached(max_age=2.5) -> Optional[float]:
    try:
        if ULTRA_CACHE.exists() and (time.time() - ULTRA_CACHE.stat().st_mtime) <= max_age:
            return float(ULTRA_CACHE.read_text().strip())
    except Exception:
        pass
    return None

class CamReader:
    def __init__(self):
        self.cap = None
        if cv2:
            try:
                cap = cv2.VideoCapture(0)
                if cap and cap.isOpened():
                    self.cap = cap
            except Exception:
                self.cap = None
    def status(self) -> str:
        return "online" if self.cap else "offline"
    def thumb_b64(self, width=160) -> Optional[str]:
        if not (self.cap and cv2): return None
        try:
            ok, frame = self.cap.read()
            if not ok: return None
            h, w = frame.shape[:2]
            scale = width / float(w)
            frame = cv2.resize(frame, (int(w*scale), int(h*scale)))
            ok, buf = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 60])
            if not ok: return None
            return base64.b64encode(buf.tobytes()).decode("ascii")
        except Exception:
            return None
    def close(self):
        try:
            if self.cap: self.cap.release()
        except Exception: pass

# ---------- MQTT (TLS + reconnect/backoff) ----------
class AIOPub:
    def __init__(self, username: str, key: str, host: str, port: int):
        self.username = username
        self.host = host
        self.port = port
        self.key  = key
        self.client = mqtt.Client(client_id="cache-telemetry", protocol=getattr(mqtt, "MQTTv311", 4))
        self.client.username_pw_set(username, key)
        # TLS on 8883 by default
        if port == 8883:
            self.client.tls_set(cert_reqs=ssl.CERT_REQUIRED)  # use system CAs
            self.client.tls_insecure_set(False)
        self.client.on_disconnect = self._on_disconnect
        self._connected = False
        self._want_run = True
        self._connect_with_backoff()

    def _connect_with_backoff(self):
        delay = 2
        while self._want_run and not self._connected:
            try:
                self.client.connect(self.host, self.port, keepalive=60)
                self.client.loop_start()
                # give it a moment to establish
                time.sleep(0.3)
                self._connected = True
            except Exception as e:
                print(f"[MQTT] connect error: {e}. retry in {delay}s")
                time.sleep(delay)
                delay = min(delay*2, 30)

    def _on_disconnect(self, _client, _userdata, rc):
        self._connected = False
        if not self._want_run: return
        # rc != 0 means unexpected — reconnect
        print(f"[MQTT] disconnected (rc={rc}). Reconnecting…")
        try:
            self.client.loop_stop()
        except Exception: pass
        self._connect_with_backoff()

    def pub(self, feed_key: str, value):
        topic = f"{self.username}/feeds/{feed_key}"
        try:
            # If we lost the link silently, try reconnect once
            if not self._connected:
                self._connect_with_backoff()
            self.client.publish(topic, str(value), qos=0, retain=False)
        except Exception as e:
            print("[MQTT] publish error:", e)

    def close(self):
        self._want_run = False
        try: self.client.loop_stop()
        except Exception: pass
        try: self.client.disconnect()
        except Exception: pass

class CsvLogger:
    def __init__(self, path: Path):
        self.path = path; path.parent.mkdir(parents=True, exist_ok=True)
        self.f = open(path,"a",newline=""); self.w = csv.writer(self.f)
        if path.stat().st_size == 0:
            self.w.writerow(["time","ultrasonic_cm","ir_left","ir_center","ir_right","line_state","camera_status"])
    def log(self, us,L,M,R,line_state,cam_status):
        self.w.writerow([now_iso(), us if us is not None else "", L, M, R, line_state, cam_status]); self.f.flush()
    def close(self):
        try: self.f.close()
        except Exception: pass

# ---------- Main loop (cache-only) ----------
class Telemetry:
    def __init__(self, cfg):
        user, key, host, port, feeds, intervals, log_cfg = load_cfg()
        self.user = user
        self.feeds = feeds
        self.pub = AIOPub(user, key, host, port)
        self.dt_ir  = intervals["infrared_sec"]
        self.dt_us  = intervals["ultrasonic_sec"]
        self.dt_cam = intervals["camera_sec"]
        self.t_ir = self.t_us = self.t_cam = 0.0
        self.cam = CamReader() if (os.environ.get("TELEM_SKIP_CAM") != "1") else None
        self.log = CsvLogger(BASE / log_cfg.get("path","logs/telemetry.csv")) if log_cfg.get("enabled",True) else None
        self.stop = False

    def loop(self):
        print("[telemetry] (cache-only, TLS) started. Ctrl+C to stop.")
        try:
            while not self.stop:
                t = time.time()

                # Ultrasonic from cache
                if t - self.t_us >= self.dt_us:
                    self.t_us = t
                    d = read_ultra_cached()
                    if d is not None:
                        self.pub.pub(self.feeds["ultrasonic_cm"], f"{d:.1f}")

                # Infrared from cache
                if t - self.t_ir >= self.dt_ir:
                    self.t_ir = t
                    v = read_ir_cached()
                    if v is not None:
                        L, M, R = v
                        self.pub.pub(self.feeds["ir_left"],   L)
                        self.pub.pub(self.feeds["ir_center"], M)
                        self.pub.pub(self.feeds["ir_right"],  R)
                        line_state = f"{'L' if L else '_'}{'M' if M else '_'}{'R' if R else '_'}"
                        self.pub.pub(self.feeds["line_state"], line_state)

                # Camera (optional, non-GPIO)
                if t - self.t_cam >= self.dt_cam:
                    self.t_cam = t
                    status = (self.cam.status() if self.cam else "offline")
                    self.pub.pub(self.feeds["camera_status"], status)
                    if self.cam:
                        thumb = self.cam.thumb_b64()
                        if thumb:
                            self.pub.pub(self.feeds["camera_thumb"], thumb)

                # Local CSV ~1Hz
                if self.log and (int(t*10)%10 == 0):
                    d = read_ultra_cached()
                    v = read_ir_cached()
                    if v: L,M,R = v; line_state = f"{'L' if L else '_'}{'M' if M else '_'}{'R' if R else '_'}"
                    else: L=M=R=""; line_state="___"
                    self.log.log(d, L, M, R, line_state, (self.cam.status() if self.cam else "offline"))

                time.sleep(0.05)
        except KeyboardInterrupt:
            print("\n[telemetry] stopping…")
        finally:
            if self.log: self.log.close()
            if self.cam: self.cam.close()
            self.pub.close()

if __name__ == "__main__":
    cfg = json.load(open(BASE/"adafruit.json"))
    Telemetry(cfg).loop()
