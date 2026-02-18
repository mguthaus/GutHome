import asyncio
import sqlite3
import struct
import time
from datetime import datetime, timezone

from bleak import BleakScanner

import config

GOVEE_MFR_KEY = 60552  # 0xEC88


def decode_h5074(mfr_data):
    """Decode Govee H5074 manufacturer data into temp_c and humidity."""
    raw = mfr_data.get(GOVEE_MFR_KEY)
    if raw is None or len(raw) < 5:
        return None, None
    temp_c = struct.unpack_from("<h", raw, 1)[0] / 100
    humidity = struct.unpack_from("<H", raw, 3)[0] / 100
    return temp_c, humidity


def init_govee_db():
    conn = sqlite3.connect(config.DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS govee_readings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            mac TEXT NOT NULL,
            room_name TEXT NOT NULL,
            temperature REAL,
            humidity REAL
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_govee_timestamp
        ON govee_readings (timestamp)
    """)
    conn.commit()
    conn.close()


async def scan_govee():
    """Scan for Govee H5074 devices and return decoded readings."""
    devices = await BleakScanner.discover(timeout=config.GOVEE_SCAN_SECONDS, return_adv=True)
    readings = {}
    for addr, (device, adv) in devices.items():
        addr_upper = addr.upper()
        if addr_upper in config.GOVEE_DEVICES:
            temp_c, humidity = decode_h5074(adv.manufacturer_data)
            if temp_c is not None:
                readings[addr_upper] = {
                    "room_name": config.GOVEE_DEVICES[addr_upper],
                    "temperature": temp_c,
                    "humidity": humidity,
                }
    return readings


def collect_govee_once():
    readings = asyncio.run(scan_govee())
    if not readings:
        print("  No Govee devices found")
        return

    conn = sqlite3.connect(config.DB_PATH)
    now = datetime.now(timezone.utc).isoformat()
    for mac, data in readings.items():
        conn.execute(
            """INSERT INTO govee_readings
               (timestamp, mac, room_name, temperature, humidity)
               VALUES (?, ?, ?, ?, ?)""",
            (now, mac, data["room_name"], data["temperature"], data["humidity"]),
        )
        temp_f = round(data["temperature"] * 9 / 5 + 32, 1)
        print(f"  {data['room_name']}: {temp_f}°F, {data['humidity']:.1f}%")
    conn.commit()
    conn.close()


def run_govee_collector():
    init_govee_db()
    print("Govee BLE collector started")
    print(f"Polling every {config.GOVEE_POLL_INTERVAL_SECONDS} seconds")
    while True:
        try:
            print(f"\nCollecting Govee at {time.strftime('%Y-%m-%d %H:%M:%S')}...")
            collect_govee_once()
        except Exception as e:
            print(f"Error collecting Govee data: {e}")
        time.sleep(config.GOVEE_POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    run_govee_collector()
