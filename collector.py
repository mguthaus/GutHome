import sqlite3
import time
import requests
import config

API_BASE = "https://home.sensibo.com/api/v2"


def init_db():
    conn = sqlite3.connect(config.DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS readings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            device_id TEXT NOT NULL,
            room_name TEXT NOT NULL,
            temperature REAL,
            humidity REAL,
            co2 INTEGER,
            tvoc INTEGER,
            iaq INTEGER
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_readings_timestamp
        ON readings (timestamp)
    """)
    conn.commit()
    conn.close()


def get_devices():
    resp = requests.get(
        f"{API_BASE}/users/me/pods",
        params={"apiKey": config.API_KEY, "fields": "id,room"},
    )
    resp.raise_for_status()
    return resp.json()["result"]


def get_measurements(device_id):
    resp = requests.get(
        f"{API_BASE}/pods/{device_id}/measurements",
        params={"apiKey": config.API_KEY},
    )
    resp.raise_for_status()
    results = resp.json()["result"]
    if results:
        return results[0]
    return None


def collect_once():
    devices = get_devices()
    conn = sqlite3.connect(config.DB_PATH)
    for device in devices:
        device_id = device["id"]
        room_name = device["room"]["name"]
        measurement = get_measurements(device_id)
        if measurement is None:
            print(f"  No data for {room_name}")
            continue
        conn.execute(
            """INSERT INTO readings
               (timestamp, device_id, room_name, temperature, humidity, co2, tvoc, iaq)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                measurement["time"]["time"],
                device_id,
                room_name,
                measurement.get("temperature"),
                measurement.get("humidity"),
                measurement.get("co2"),
                measurement.get("tvoc"),
                measurement.get("iaq"),
            ),
        )
        temp_f = measurement.get('temperature')
        if temp_f is not None:
            temp_f = round(temp_f * 9 / 5 + 32, 1)
        print(
            f"  {room_name}: {temp_f}°F, "
            f"CO2={measurement.get('co2')}, TVOC={measurement.get('tvoc')}"
        )
    conn.commit()
    conn.close()


def run_collector():
    init_db()
    print("Sensibo data collector started")
    print(f"Polling every {config.POLL_INTERVAL_SECONDS} seconds")
    while True:
        try:
            print(f"\nCollecting at {time.strftime('%Y-%m-%d %H:%M:%S')}...")
            collect_once()
        except Exception as e:
            print(f"Error collecting data: {e}")
        time.sleep(config.POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    run_collector()
