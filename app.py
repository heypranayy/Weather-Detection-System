from flask import Flask, render_template, jsonify, request
import requests
from stations import STATIONS

app = Flask(__name__)

# WMO weather codes -> short labels (Open-Meteo)
WEATHER_CODES = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Depositing rime fog",
    51: "Light drizzle",
    53: "Moderate drizzle",
    55: "Dense drizzle",
    61: "Slight rain",
    63: "Moderate rain",
    65: "Heavy rain",
    71: "Slight snow",
    73: "Moderate snow",
    75: "Heavy snow",
    80: "Slight rain showers",
    81: "Moderate rain showers",
    82: "Violent rain showers",
    95: "Thunderstorm",
    96: "Thunderstorm with slight hail",
    99: "Thunderstorm with heavy hail",
}

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/api/stations", methods=["GET"])
def get_stations():
    # Frontend only needs names (+ district for display hints)
    return jsonify(
        {
            name: {"district": info["district"]}
            for name, info in STATIONS.items()
        }
    )


@app.route("/api/weather", methods=["GET"])
def get_weather():
    station_name = (request.args.get("station") or "").strip().upper()

    if not station_name:
        return jsonify({"status": "error", "message": "No station name provided"}), 400

    station = None
    display_name = None
    for name, info in STATIONS.items():
        if name.upper() == station_name:
            station = info
            display_name = name
            break

    if not station:
        return jsonify({"status": "error", "message": "Station not found in West Bengal list"}), 404

    params = {
        "latitude": station["lat"],
        "longitude": station["lon"],
        "current": (
            "temperature_2m,relative_humidity_2m,wind_speed_10m,"
            "weather_code,precipitation,apparent_temperature"
        ),
        "timezone": "Asia/Kolkata",
        "wind_speed_unit": "kmh",
    }

    try:
        response = requests.get(OPEN_METEO_URL, params=params, timeout=10)
        response.raise_for_status()
        payload = response.json()
        current = payload.get("current", {})

        weather_code = current.get("weather_code")
        condition = WEATHER_CODES.get(weather_code, f"Code {weather_code}")

        return jsonify(
            {
                "status": "success",
                "data": {
                    "Station": display_name,
                    "District": station["district"],
                    "Temperature": current.get("temperature_2m"),
                    "Feels Like": current.get("apparent_temperature"),
                    "Relative Humidity": current.get("relative_humidity_2m"),
                    "Wind Speed": current.get("wind_speed_10m"),
                    "Precipitation": current.get("precipitation"),
                    "Condition": condition,
                    "Observed At": current.get("time"),
                    "Latitude": station["lat"],
                    "Longitude": station["lon"],
                },
                "source": "Open-Meteo",
            }
        )
    except requests.exceptions.RequestException as e:
        return jsonify({"status": "error", "message": str(e)}), 500


if __name__ == "__main__":
    app.run(debug=True, port=5000)
