import sqlite3
import time
from datetime import datetime, timezone

import requests
import urllib3

import config

# Suppress SSL warnings for local Envoy
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def init_solar_db():
    conn = sqlite3.connect(config.DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS solar_readings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            production_w REAL,
            consumption_w REAL,
            net_consumption_w REAL,
            production_wh_today REAL,
            consumption_wh_today REAL,
            production_wh_lifetime REAL,
            imported_wh_today REAL,
            exported_wh_today REAL
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_solar_timestamp
        ON solar_readings (timestamp)
    """)
    # Add columns if upgrading from old schema
    for col in ("imported_wh_today", "exported_wh_today"):
        try:
            conn.execute(f"ALTER TABLE solar_readings ADD COLUMN {col} REAL")
        except sqlite3.OperationalError:
            pass  # column already exists
    conn.commit()
    conn.close()


def _fetch_with_retries(max_retries=3, retry_delay=10):
    """Fetch from Enphase gateway with retries on connection failure."""
    for attempt in range(max_retries):
        try:
            resp = requests.get(
                f"https://{config.ENPHASE_HOST}/production.json?details=1",
                headers={"Authorization": f"Bearer {config.ENPHASE_TOKEN}"},
                verify=False,
                timeout=10,
            )
            resp.raise_for_status()
            return resp.json()
        except (requests.ConnectionError, requests.Timeout) as e:
            if attempt < max_retries - 1:
                print(f"  Retry {attempt + 1}/{max_retries} after error: {e}")
                time.sleep(retry_delay)
            else:
                raise


def collect_solar_once():
    data = _fetch_with_retries()

    production = None
    consumption = None
    net = None
    prod_today = None
    cons_today = None
    prod_lifetime = None

    for p in data.get("production", []):
        if p.get("measurementType") == "production":
            production = p["wNow"]
            prod_today = p.get("whToday")
            prod_lifetime = p.get("whLifetime")

    for c in data.get("consumption", []):
        if c.get("measurementType") == "total-consumption":
            consumption = c["wNow"]
            # Sum per-line whToday to avoid split-phase double-counting bug
            lines = c.get("lines", [])
            if lines:
                cons_today = sum(line.get("whToday", 0) for line in lines)
            else:
                cons_today = c.get("whToday")
        elif c.get("measurementType") == "net-consumption":
            net = c["wNow"]

    now = datetime.now(timezone.utc).isoformat()
    conn = sqlite3.connect(config.DB_PATH)
    conn.execute(
        """INSERT INTO solar_readings
           (timestamp, production_w, consumption_w, net_consumption_w,
            production_wh_today, consumption_wh_today, production_wh_lifetime)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (now, production, consumption, net, prod_today, cons_today, prod_lifetime),
    )
    conn.commit()
    conn.close()

    prod_kw = production / 1000 if production else 0
    cons_kw = consumption / 1000 if consumption else 0
    print(
        f"  Solar: Production {prod_kw:.2f}kW, "
        f"Consumption {cons_kw:.2f}kW, "
        f"Today {(prod_today or 0) / 1000:.1f}kWh"
    )


def run_solar_collector():
    init_solar_db()
    print("Enphase solar collector started")
    print(f"Polling every {config.ENPHASE_POLL_INTERVAL_SECONDS} seconds")
    while True:
        try:
            print(f"\nCollecting solar at {time.strftime('%Y-%m-%d %H:%M:%S')}...")
            collect_solar_once()
        except Exception as e:
            print(f"Error collecting solar data: {e}")
        time.sleep(config.ENPHASE_POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    run_solar_collector()
