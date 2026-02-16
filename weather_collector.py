import sqlite3
import time

import requests

import config

WU_API_URL = "https://api.weather.com/v2/pws/observations/current"
WU_API_KEY = "6532d6454b8aa370768e63d6ba5a832e"
AQI_API_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"


def init_weather_db():
    conn = sqlite3.connect(config.DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS weather_readings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            station_id TEXT NOT NULL,
            temperature REAL,
            humidity REAL,
            dewpoint REAL,
            wind_speed REAL,
            wind_gust REAL,
            wind_dir INTEGER,
            pressure REAL,
            precip_rate REAL,
            precip_total REAL,
            solar_radiation REAL,
            uv REAL,
            aqi INTEGER,
            pm25 REAL,
            pm10 REAL
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_weather_timestamp
        ON weather_readings (timestamp)
    """)
    conn.commit()
    conn.close()


def get_aqi(lat, lon):
    """Fetch current AQI from Open-Meteo (no API key needed)."""
    try:
        resp = requests.get(
            AQI_API_URL,
            params={
                "latitude": lat,
                "longitude": lon,
                "current": "us_aqi,pm2_5,pm10",
            },
        )
        resp.raise_for_status()
        current = resp.json()["current"]
        return current["us_aqi"], current["pm2_5"], current["pm10"]
    except Exception as e:
        print(f"  AQI fetch error: {e}")
        return None, None, None


def collect_weather_once():
    resp = requests.get(
        WU_API_URL,
        params={
            "stationId": config.WU_STATION_ID,
            "format": "json",
            "units": "e",
            "apiKey": WU_API_KEY,
        },
    )
    resp.raise_for_status()
    obs = resp.json()["observations"][0]
    imp = obs["imperial"]

    aqi, pm25, pm10 = get_aqi(obs["lat"], obs["lon"])

    conn = sqlite3.connect(config.DB_PATH)
    conn.execute(
        """INSERT INTO weather_readings
           (timestamp, station_id, temperature, humidity, dewpoint,
            wind_speed, wind_gust, wind_dir, pressure,
            precip_rate, precip_total, solar_radiation, uv,
            aqi, pm25, pm10)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            obs["obsTimeUtc"],
            obs["stationID"],
            imp["temp"],
            obs["humidity"],
            imp["dewpt"],
            imp["windSpeed"],
            imp["windGust"],
            obs["winddir"],
            imp["pressure"],
            imp["precipRate"],
            imp["precipTotal"],
            obs.get("solarRadiation"),
            obs.get("uv"),
            aqi,
            pm25,
            pm10,
        ),
    )
    conn.commit()
    conn.close()
    print(
        f"  Outside: {imp['temp']}°F, {obs['humidity']}% humidity, "
        f"Wind {imp['windSpeed']}mph, Rain {imp['precipRate']}in/hr, "
        f"AQI {aqi}"
    )


def run_weather_collector():
    init_weather_db()
    print("Weather Underground collector started")
    print(f"Polling every {config.WU_POLL_INTERVAL_SECONDS} seconds")
    while True:
        try:
            print(f"\nCollecting weather at {time.strftime('%Y-%m-%d %H:%M:%S')}...")
            collect_weather_once()
        except Exception as e:
            print(f"Error collecting weather data: {e}")
        time.sleep(config.WU_POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    run_weather_collector()
