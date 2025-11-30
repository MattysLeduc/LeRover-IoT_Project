#!/usr/bin/env python3
"""
Database Sync Module
Handles local SQLite database and sync with cloud database (Neon.com)
"""
import sqlite3
import os
import json
import time
import sys
from pathlib import Path
from datetime import datetime
import psycopg2
from psycopg2.extras import execute_values

BASE_DIR = Path(__file__).parent.parent
DB_DIR = BASE_DIR / "db"
DB_DIR.mkdir(exist_ok=True)
LOCAL_DB = DB_DIR / "robot_telemetry.db"
SYNC_STATUS_FILE = DB_DIR / "sync_status.json"

def init_local_db():
    """Initialize local SQLite database"""
    conn = sqlite3.connect(LOCAL_DB)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS sensor_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            ultrasonic_cm REAL,
            ir_left INTEGER,
            ir_center INTEGER,
            ir_right INTEGER,
            line_state TEXT,
            synced INTEGER DEFAULT 0,
            sync_timestamp TEXT
        )
    ''')
    # Create index for faster queries
    c.execute('CREATE INDEX IF NOT EXISTS idx_timestamp ON sensor_data(timestamp)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_synced ON sensor_data(synced)')
    conn.commit()
    conn.close()

def save_to_local_db(timestamp, ultrasonic=None, ir_left=None, ir_center=None, ir_right=None, line_state=None):
    """Save sensor data to local SQLite database"""
    try:
        conn = sqlite3.connect(LOCAL_DB)
        c = conn.cursor()
        c.execute('''
            INSERT INTO sensor_data (timestamp, ultrasonic_cm, ir_left, ir_center, ir_right, line_state, synced)
            VALUES (?, ?, ?, ?, ?, ?, 0)
        ''', (timestamp, ultrasonic, ir_left, ir_center, ir_right, line_state))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Error saving to local DB: {e}")
        return False

def get_unsynced_records():
    """Get all unsynced records from local database"""
    try:
        conn = sqlite3.connect(LOCAL_DB)
        c = conn.cursor()
        c.execute('SELECT id, timestamp, ultrasonic_cm, ir_left, ir_center, ir_right, line_state FROM sensor_data WHERE synced = 0 ORDER BY id')
        records = c.fetchall()
        conn.close()
        return records
    except Exception as e:
        print(f"Error getting unsynced records: {e}")
        return []

def mark_as_synced(record_ids):
    """Mark records as synced"""
    try:
        conn = sqlite3.connect(LOCAL_DB)
        c = conn.cursor()
        sync_time = datetime.now().isoformat()
        placeholders = ','.join('?' * len(record_ids))
        c.execute(f'UPDATE sensor_data SET synced = 1, sync_timestamp = ? WHERE id IN ({placeholders})', 
                 [sync_time] + list(record_ids))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Error marking as synced: {e}")
        return False

def get_cloud_connection():
    """Get connection to cloud database with proper error handling"""
    cloud_db_url = os.environ.get("DATABASE_URL", "")
    if not cloud_db_url:
        return None, "No DATABASE_URL set"
    
    try:
        # Parse connection string and ensure SSL is properly configured
        # Neon.com requires SSL connections
        # Check if sslmode is already in the URL
        if "sslmode" not in cloud_db_url.lower():
            # Add sslmode if not present
            separator = "&" if "?" in cloud_db_url else "?"
            cloud_db_url = f"{cloud_db_url}{separator}sslmode=require"
        
        # Connect with timeout
        # Note: sslmode in connection string takes precedence over parameter
        conn = psycopg2.connect(
            cloud_db_url,
            connect_timeout=10
        )
        return conn, None
    except psycopg2.OperationalError as e:
        return None, f"Connection error: {e}"
    except psycopg2.Error as e:
        return None, f"Database error: {e}"
    except Exception as e:
        return None, f"Unexpected error: {e}"

def sync_to_cloud():
    """Sync unsynced records to cloud database (Neon.com)"""
    cloud_db_url = os.environ.get("DATABASE_URL", "")
    if not cloud_db_url:
        print("No DATABASE_URL set, skipping cloud sync", file=sys.stderr)
        return False
    
    unsynced = get_unsynced_records()
    if not unsynced:
        return True
    
    print(f"[sync] Found {len(unsynced)} unsynced records to sync", file=sys.stderr)
    
    conn, error = get_cloud_connection()
    if conn is None:
        print(f"[sync] Failed to connect to cloud database: {error}", file=sys.stderr)
        return False
    
    try:
        c = conn.cursor()
        
        # Ensure table exists with proper schema
        c.execute('''
            CREATE TABLE IF NOT EXISTS sensor_data (
                id SERIAL PRIMARY KEY,
                timestamp TIMESTAMP NOT NULL,
                ultrasonic_cm REAL,
                ir_left INTEGER,
                ir_center INTEGER,
                ir_right INTEGER,
                line_state TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create unique constraint for ON CONFLICT to work
        # Check if constraint already exists
        c.execute('''
            SELECT 1 FROM pg_constraint 
            WHERE conname = 'sensor_data_unique'
        ''')
        constraint_exists = c.fetchone()
        
        if not constraint_exists:
            try:
                # Create unique constraint
                c.execute('''
                    ALTER TABLE sensor_data 
                    ADD CONSTRAINT sensor_data_unique 
                    UNIQUE (timestamp, ultrasonic_cm, ir_left, ir_center, ir_right, line_state)
                ''')
            except Exception as e:
                # If constraint creation fails (e.g., duplicates exist), create unique index instead
                try:
                    c.execute('''
                        CREATE UNIQUE INDEX IF NOT EXISTS sensor_data_unique_idx 
                        ON sensor_data (timestamp, ultrasonic_cm, ir_left, ir_center, ir_right, line_state)
                    ''')
                except Exception:
                    pass  # Index might already exist
        
        conn.commit()
        
        # Insert unsynced records (skip duplicates)
        # Convert SQLite timestamp strings to PostgreSQL TIMESTAMP
        records = []
        for r in unsynced:
            try:
                # Parse timestamp string to datetime object
                timestamp_str = r[1]  # timestamp is at index 1
                if isinstance(timestamp_str, str):
                    # Try to parse ISO format timestamp
                    dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                else:
                    dt = timestamp_str
                
                records.append((
                    dt,
                    r[2] if r[2] is not None else None,  # ultrasonic_cm
                    r[3] if r[3] is not None else None,  # ir_left
                    r[4] if r[4] is not None else None,  # ir_center
                    r[5] if r[5] is not None else None,  # ir_right
                    r[6] if r[6] else None  # line_state
                ))
            except Exception as e:
                print(f"Warning: Skipping record {r[0]} due to timestamp error: {e}")
                continue
        
        if not records:
            conn.close()
            return True
        
        # Use ON CONFLICT - try constraint name first, then column list
        inserted_count = 0
        try:
            # Try with constraint name first
            execute_values(
                c,
                '''INSERT INTO sensor_data (timestamp, ultrasonic_cm, ir_left, ir_center, ir_right, line_state)
                   VALUES %s 
                   ON CONFLICT ON CONSTRAINT sensor_data_unique 
                   DO NOTHING''',
                records
            )
            inserted_count = c.rowcount
            print(f"[sync] Inserted {inserted_count} records (constraint method)", file=sys.stderr)
        except Exception as e1:
            # Fallback: use column list (works with unique index too)
            # This handles cases where constraint doesn't exist or has different name
            try:
                execute_values(
                    c,
                    '''INSERT INTO sensor_data (timestamp, ultrasonic_cm, ir_left, ir_center, ir_right, line_state)
                       VALUES %s 
                       ON CONFLICT (timestamp, ultrasonic_cm, ir_left, ir_center, ir_right, line_state) 
                       DO NOTHING''',
                    records
                )
                inserted_count = c.rowcount
                print(f"[sync] Inserted {inserted_count} records (column list method)", file=sys.stderr)
            except Exception as e2:
                print(f"[sync] ERROR inserting records (constraint): {e1}", file=sys.stderr)
                print(f"[sync] ERROR inserting records (column list): {e2}", file=sys.stderr)
                import traceback
                print(f"[sync] Traceback: {traceback.format_exc()}", file=sys.stderr)
                conn.rollback()
                conn.close()
                return False
        
        conn.commit()
        
        # Mark as synced only if insert was successful
        # Mark all records that were prepared (even if some were duplicates and not inserted)
        record_ids = [r[0] for r in unsynced]
        if record_ids:
            mark_as_synced(record_ids)
            print(f"[sync] Marked {len(record_ids)} records as synced", file=sys.stderr)
        
        conn.close()
        
        print(f"[sync] Successfully synced {len(records)} records to cloud (inserted: {inserted_count}, duplicates skipped: {len(records) - inserted_count}) at {datetime.now().strftime('%H:%M:%S')}", file=sys.stderr)
        return True
    except Exception as e:
        print(f"Error syncing to cloud: {e}")
        try:
            conn.rollback()
            conn.close()
        except:
            pass
        return False

def check_internet():
    """Check if internet connection is available"""
    try:
        import socket
        socket.create_connection(("8.8.8.8", 53), timeout=3)
        return True
    except OSError:
        return False

def sync_worker():
    """Background worker to periodically sync data"""
    init_local_db()
    while True:
        if check_internet():
            sync_to_cloud()
        time.sleep(300)  # Sync every 5 minutes

if __name__ == "__main__":
    # Initialize database
    init_local_db()
    
    # Try to sync immediately
    if check_internet():
        sync_to_cloud()
    else:
        print("No internet connection, data will be synced when connection is restored")

