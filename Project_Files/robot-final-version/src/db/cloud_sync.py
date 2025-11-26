#!/usr/bin/env python3
import sqlite3
import psycopg2
import time
from datetime import datetime
from pathlib import Path
import json

BASE = Path(__file__).resolve().parent.parent
LOCAL_DB = BASE / "data" / "local_telemetry.sqlite3"
CFG_FILE = BASE / "config" / "cloud.json"

def load_cfg():
    return json.loads(CFG_FILE.read_text())

def read_unsynced_rows(limit=200):
    conn = sqlite3.connect(LOCAL_DB)
    cur = conn.cursor()
    cur.execute("""
        SELECT id, timestamp_iso, ultrasonic_cm, ir_left, ir_center, ir_right, line_state
        FROM robot_data
        WHERE synced = 0
        ORDER BY id ASC
        LIMIT ?;
    """, (limit,))
    rows = cur.fetchall()
    conn.close()
    return rows

def mark_synced(ids):
    conn = sqlite3.connect(LOCAL_DB)
    cur = conn.cursor()
    cur.executemany("UPDATE robot_data SET synced=1 WHERE id=?", [(i,) for i in ids])
    conn.commit()
    conn.close()

def send_to_neon(rows):
    cfg = load_cfg()
    url = cfg["postgres_url"]

    conn = psycopg2.connect(url)
    cur = conn.cursor()

    for row in rows:
        id_, ts, u, L, M, R, state = row
        cur.execute("""
            INSERT INTO robot_data (timestamp, ultrasonic, ir_left, ir_center, ir_right, line_state)
            VALUES (%s, %s, %s, %s, %s, %s);
        """, (ts, u, L, M, R, state))

    conn.commit()
    conn.close()

def main():
    print("[cloud-sync] running… CTRL+C to exit")
    while True:
        rows = read_unsynced_rows()
        if rows:
            print(f"[cloud-sync] syncing {len(rows)} rows…")
            send_to_neon(rows)
            mark_synced([r[0] for r in rows])
        else:
            print("[cloud-sync] nothing to sync")
        time.sleep(10)

if __name__ == "__main__":
    main()
