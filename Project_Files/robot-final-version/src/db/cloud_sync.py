#!/usr/bin/env python3
import sqlite3
import psycopg2
from pathlib import Path

# ---------------------------------------
# Paths
# ---------------------------------------
BASE = Path(__file__).resolve().parents[1]
SQLITE_PATH = BASE / "data" / "local_telemetry.sqlite3"

# ---------------------------------------
# Neon connection
# ---------------------------------------
NEON_URL = "postgresql://neondb_owner:npg_i9VqpD6REewK@ep-lively-pine-adzerwla-pooler.c-2.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"

# ---------------------------------------
# Read newest rows that are not in Neon
# ---------------------------------------
def read_local_rows(last_id):
    conn = sqlite3.connect(SQLITE_PATH)
    cur = conn.cursor()

    cur.execute("""
        SELECT id, timestamp_utc, ultrasonic_cm, ir_left, ir_center, ir_right, line_state
        FROM robot_data
        WHERE id > ?
        ORDER BY id ASC;
    """, (last_id,))

    rows = cur.fetchall()
    conn.close()
    return rows

# ---------------------------------------
# Get last synced ID from NeonDB
# ---------------------------------------
def get_last_neon_id(pg_cur):
    pg_cur.execute("SELECT COALESCE(MAX(id), 0) FROM robot_data;")
    return pg_cur.fetchone()[0]

# ---------------------------------------
# Upload a batch of rows
# ---------------------------------------
def upload_rows(pg_cur, rows):
    for row in rows:
        pg_cur.execute("""
            INSERT INTO robot_data
            (id, timestamp, ultrasonic, ir_left, ir_center, ir_right, line_state)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO NOTHING;
        """, row)

# ---------------------------------------
# MAIN
# ---------------------------------------
def main():
    print("[cloud-sync] running... press Ctrl+C to stop")

    # Connect to Neon
    pg = psycopg2.connect(NEON_URL)
    pg_cur = pg.cursor()

    # 1. find last synced ID in Neon
    last_id = get_last_neon_id(pg_cur)
    print(f"[cloud-sync] Last ID in Neon = {last_id}")

    # 2. read new rows from SQLite
    rows = read_local_rows(last_id)
    print(f"[cloud-sync] Found {len(rows)} new rows to upload")

    if rows:
        upload_rows(pg_cur, rows)
        pg.commit()
        print(f"[cloud-sync] Uploaded {len(rows)} rows -> Neon")

    pg_cur.close()
    pg.close()
    print("[cloud-sync] Done.")


if __name__ == "__main__":
    main()
