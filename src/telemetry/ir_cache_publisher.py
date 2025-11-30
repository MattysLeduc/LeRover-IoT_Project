#!/usr/bin/env python3
"""
IR cache → Adafruit IO publisher

- Reads IR state from /tmp/ir_triplet.txt (preferred) or /tmp/line_state.txt
- Publishes to Adafruit IO MQTT using credentials in adafruit.json
  (supports nested {"adafruit": {...}} OR flat keys)
- Compatible with paho-mqtt 1.x and 2.x
"""

import os
import time
import json
from pathlib import Path
import paho.mqtt.client as mqtt

# ---- Cache files -------------------------------------------------------------
IR_TRIP  = Path("/tmp/ir_triplet.txt")  # either "0 1 0" or "0,1,0"
LINEFILE = Path("/tmp/line_state.txt")  # "LMR", "LM", "R", "NONE", etc.

# ---- Config loading ----------------------------------------------------------
def load_cfg():
    """
    Returns:
      (username, key, host, port, feeds) tuple
    """
    cfg = json.loads(Path("adafruit.json").read_text())

    # Accept both nested and flat
    if isinstance(cfg, dict) and "adafruit" in cfg:
        a = cfg["adafruit"]
        username = a.get("username") or a.get("user") or os.getenv("AIO_USERNAME")
        key      = a.get("key")      or a.get("aio_key") or os.getenv("AIO_KEY")
        host     = a.get("host", "io.adafruit.com")
        port     = int(a.get("port", 1883))
        feeds    = a.get("feeds", {})
    else:
        username = cfg.get("username") or cfg.get("user") or os.getenv("AIO_USERNAME")
        key      = cfg.get("key")      or cfg.get("aio_key") or os.getenv("AIO_KEY")
        host     = cfg.get("host", "io.adafruit.com")
        port     = int(cfg.get("port", 1883))
        feeds    = cfg.get("feeds", {})

    if not username or not key:
        raise RuntimeError("Missing AIO username/key (check adafruit.json or env AIO_USERNAME/AIO_KEY).")

    required = ("ir_left","ir_center","ir_right","line_state")
    for k in required:
        if k not in feeds:
            raise RuntimeError(f"Config missing feeds['{k}'].")

    return username, key, host, port, feeds

# ---- Cache reading helpers ---------------------------------------------------
def _parse_trip(text: str):
    """Accept '0 1 0' or '0,1,0' → (L,M,R) ints, or None if invalid."""
    if not text:
        return None
    t = text.replace(",", " ").split()
    if len(t) != 3:
        return None
    try:
        L, M, R = [int(bool(int(x))) for x in t]
        return L, M, R
    except Exception:
        return None

def parse_line_state(s: str):
    s = (s or "").strip().upper()
    L = 1 if "L" in s else 0
    M = 1 if "M" in s else 0
    R = 1 if "R" in s else 0
    return L, M, R

def read_cache():
    """Return (L, M, R, state_string)."""
    if IR_TRIP.exists():
        try:
            trip = IR_TRIP.read_text().strip()
            v = _parse_trip(trip)
            if v:
                L, M, R = v
                state = "".join([c for c, b in zip("LMR", (L, M, R)) if b]) or "NONE"
                return L, M, R, state
        except Exception:
            pass
    # Fallback to symbolic state file
    ls = LINEFILE.read_text().strip() if LINEFILE.exists() else ""
    L, M, R = parse_line_state(ls)
    state = ls or ("NONE" if (L, M, R) == (0, 0, 0) else "".join([c for c, b in zip("LMR", (L, M, R)) if b]))
    return L, M, R, state

# ---- MQTT --------------------------------------------------------------------
def make_client(username: str, key: str, host: str, port: int):
    # paho-mqtt compatibility (1.x vs 2.x)
    try:
        client = mqtt.Client(client_id="ir-cache-pub")
    except TypeError:
        # very old signature
        client = mqtt.Client("ir-cache-pub")
    client.username_pw_set(username, key)
    client.connect(host, port, keepalive=30)
    client.loop_start()
    return client

def build_topics(username: str, feeds: dict):
    base = f"{username}/feeds"
    return {
        "L": f"{base}/{feeds['ir_left']}",
        "M": f"{base}/{feeds['ir_center']}",
        "R": f"{base}/{feeds['ir_right']}",
        "S": f"{base}/{feeds['line_state']}",
    }

# ---- Main --------------------------------------------------------------------
def main():
    # Optional ENV controls
    interval = float(os.getenv("IR_PUB_INTERVAL", "0.2"))
    retain   = os.getenv("IR_PUB_RETAIN", "0") == "1"
    debug    = os.getenv("IR_PUB_DEBUG",  "1") == "1"

    username, key, host, port, feeds = load_cfg()
    topics = build_topics(username, feeds)
    client = make_client(username, key, host, port)

    try:
        if debug:
            print(f"[IR→AIO] publishing to mqtt://{host}:{port} as {username}")
            for k, v in topics.items():
                print(f"  topic[{k}] = {v}")

        while True:
            L, M, R, state = read_cache()
            # publish
            client.publish(topics["L"], str(L), qos=0, retain=retain)
            client.publish(topics["M"], str(M), qos=0, retain=retain)
            client.publish(topics["R"], str(R), qos=0, retain=retain)
            client.publish(topics["S"], state,  qos=0, retain=retain)
            if debug:
                print(f"[IR→AIO] L={L} M={M} R={R} state={state}")
            time.sleep(interval)
    except KeyboardInterrupt:
        pass
    finally:
        try: client.loop_stop()
        except Exception: pass
        try: client.disconnect()
        except Exception: pass

if __name__ == "__main__":
    main()
