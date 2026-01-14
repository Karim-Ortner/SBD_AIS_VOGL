import os
import subprocess
import sys
import time
from datetime import datetime, timedelta
import psycopg2
from psycopg2 import sql

DB_NAME = os.getenv("OFFICE_DB", "office_db")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "postgrespw")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
SENSOR_ID = os.getenv("SENSOR_ID")  # optional: filter by specific sensor

def get_connection():
    return psycopg2.connect(
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        host=DB_HOST,
        port=DB_PORT,
    )

# -------------------------
# Periodically compute average over last 10 minutes
# -------------------------
conn = None
try:
    conn = get_connection()
    while True:
        ten_minutes_ago = datetime.now() - timedelta(minutes=10)
        with conn.cursor() as cur:
            if SENSOR_ID:
                cur.execute(
                    """
                    SELECT AVG(temperature)
                    FROM temperature_readings
                    WHERE sensor_id = %s AND recorded_at >= %s
                    """,
                    (SENSOR_ID, ten_minutes_ago),
                )
            else:
                cur.execute(
                    """
                    SELECT AVG(temperature)
                    FROM temperature_readings
                    WHERE recorded_at >= %s
                    """,
                    (ten_minutes_ago,),
                )
            row = cur.fetchone()
            avg_temp = row[0] if row else None
        if avg_temp is not None:
            print(f"{datetime.now()} - Average temperature last 10 minutes: {avg_temp:.2f} °C")
        else:
            print(f"{datetime.now()} - No data in last 10 minutes.")
        time.sleep(600)  # every 10 minutes
except KeyboardInterrupt:
    print("Stopped consuming data.")
except Exception as e:
    print(f"Error while consuming data: {e}")
finally:
    try:
        if conn:
            conn.close()
    except Exception:
        pass
    print("Exiting.")
