# src/db/local_db.py
import sqlite3
from pathlib import Path
from datetime import datetime

# Database path: /src/data/local_telemetry.sqlite3
BASE = Path(__file__).resolve().parents[1]   # /src
DB_PATH = BASE / "data" / "local_telemetry.sqlite3"

# SQLite schema
SCHEMA = """
CREATE TABLE IF NOT EXISTS robot_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp_utc TEXT NOT NULL,
    ultrasonic_cm REAL,
    ir_left INTEGER,
    ir_center INTEGER,
    ir_right INTEGER,
    line_state TEXT
);
"""

def get_conn():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute(SCHEMA)
    return conn

def insert_row(ts_utc, ultra, L, M, R, state):
    conn = get_conn()
    try:
        conn.execute(
            """
            INSERT INTO robot_data
            (timestamp_utc, ultrasonic_cm, ir_left, ir_center, ir_right, line_state)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                ts_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
                None if ultra is None else float(ultra),
                None if L is None else int(L),
                None if M is None else int(M),
                None if R is None else int(R),
                state
            ),
        )
        conn.commit()
    finally:
        conn.close()
