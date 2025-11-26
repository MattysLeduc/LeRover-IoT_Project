# src/db/local_db.py
import sqlite3
from pathlib import Path
from datetime import datetime

BASE = Path(__file__).resolve().parents[1]  # .../src
DB_PATH = BASE / "data" / "local_telemetry.sqlite3"

SCHEMA = """
CREATE TABLE IF NOT EXISTS robot_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp_utc TEXT NOT NULL,
    ultrasonic_cm REAL,
    ir_left INTEGER,
    ir_center INTEGER,
    ir_right INTEGER,
    line_state TEXT,
    synced INTEGER DEFAULT 0
);
"""

def get_conn():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute(SCHEMA)
    return conn

def insert_row(ts_utc: datetime, ultra, L, M, R, state: str):
    conn = get_conn()
    try:
        conn.execute(
            "INSERT INTO robot_data (timestamp_utc, ultrasonic_cm, ir_left, ir_center, ir_right, line_state, synced) "
            "VALUES (?, ?, ?, ?, ?, ?, 0)",
            (
                ts_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
                None if ultra is None else float(ultra),
                None if L is None else int(L),
                None if M is None else int(M),
                None if R is None else int(R),
                state,
            ),
        )
        conn.commit()
    finally:
        conn.close()

def fetch_unsynced(limit=500):
    conn = get_conn()
    try:
        cur = conn.execute(
            "SELECT id, timestamp_utc, ultrasonic_cm, ir_left, ir_center, ir_right, line_state "
            "FROM robot_data WHERE synced = 0 ORDER BY id ASC LIMIT ?",
            (limit,),
        )
        rows = cur.fetchall()
        return rows
    finally:
        conn.close()

def mark_synced(ids):
    if not ids:
        return
    conn = get_conn()
    try:
        conn.execute(
            "UPDATE robot_data SET synced = 1 WHERE id IN (%s)" %
            ",".join("?" for _ in ids),
            tuple(ids),
        )
        conn.commit()
    finally:
        conn.close()
