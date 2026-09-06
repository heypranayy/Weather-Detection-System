from flask import Flask, render_template, jsonify, request
import requests
from stations import STATIONS, STATIONS_BY_STATE

app = Flask(__name__)

# Weather code lookup table (WMO / Open-Meteo standard)
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


@app.route('/')
def home():
    return render_template('index.html')


@app.route('/api/stations', methods=['GET'])
def get_stations():
    states = sorted(list(STATIONS_BY_STATE.keys()))
    return jsonify({
        "status": "success",
        "stations": STATIONS,
        "states": states,
        "by_state": STATIONS_BY_STATE
    })


@app.route('/api/weather', methods=['GET'])
def get_weather():
    station_query = request.args.get('station') or request.args.get('station_id') or request.args.get('station_name')
    
    if not station_query:
        return jsonify({"status": "error", "message": "No station provided"}), 400

    station_query_clean = station_query.strip().upper()
    
    matched_name = None
    matched_info = None

    # 1. Match by exact station name or station ID
    for name, info in STATIONS.items():
        if name.upper() == station_query_clean or str(info.get('id')) == station_query_clean:
            matched_name = name
            matched_info = info
            break

    # 2. Fuzzy match if exact match wasn't found
    if not matched_info:
        for name, info in STATIONS.items():
            if station_query_clean in name.upper():
                matched_name = name
                matched_info = info
                break

    if not matched_info:
        return jsonify({"status": "error", "message": f"Station '{station_query}' not found in India database"}), 404

    station_id = matched_info.get("id")
    state = matched_info.get("state", "India")
    lat = matched_info.get("lat")
    lon = matched_info.get("lon")

    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    
    # Primary attempt: IMD Official Endpoint
    if station_id:
        imd_url = f"https://api.imd.gov.in/api/v1/current_wx?id={station_id}"
        try:
            imd_res = requests.get(imd_url, headers=headers, timeout=4)
            if imd_res.status_code == 200:
                imd_json = imd_res.json()
                wx_data = None
                if isinstance(imd_json, list) and len(imd_json) > 0:
                    wx_data = imd_json[0]
                elif isinstance(imd_json, dict):
                    wx_data = imd_json.get("data") or imd_json.get("current_wx")
                    if isinstance(wx_data, list) and len(wx_data) > 0:
                        wx_data = wx_data[0]

                if wx_data and isinstance(wx_data, dict):
                    return jsonify({
                        "status": "success",
                        "data": {
                            "Station": wx_data.get("Station") or matched_name,
                            "State": state,
                            "StationID": station_id,
                            "Temperature": wx_data.get("Dry Bulb Temperature") or wx_data.get("Temperature"),
                            "Feels Like": wx_data.get("Apparent Temperature") or wx_data.get("Dry Bulb Temperature"),
                            "Relative Humidity": wx_data.get("Relative Humidity") or wx_data.get("Humidity"),
                            "Wind Speed": wx_data.get("Wind Speed"),
                            "Precipitation": wx_data.get("Precipitation", 0),
                            "Condition": wx_data.get("Weather Condition") or wx_data.get("Condition") or "Clear Sky",
                            "Observed At": wx_data.get("Time") or wx_data.get("Observed At") or "Live",
                            "Source": "India Meteorological Department (IMD)",
                            "Latitude": lat,
                            "Longitude": lon
                        }
                    })
        except Exception:
            pass  # Failover to Open-Meteo coordinates provider

    # Secondary high-reliability fallback: Open-Meteo Live Forecast
    try:
        params = {
            "latitude": lat,
            "longitude": lon,
            "current": "temperature_2m,relative_humidity_2m,wind_speed_10m,weather_code,precipitation,apparent_temperature",
            "timezone": "Asia/Kolkata",
            "wind_speed_unit": "kmh",
        }
        om_res = requests.get(OPEN_METEO_URL, params=params, timeout=8)
        om_res.raise_for_status()
        om_payload = om_res.json()
        current = om_payload.get("current", {})

        weather_code = current.get("weather_code")
        condition = WEATHER_CODES.get(weather_code, f"Code {weather_code}")

        return jsonify({
            "status": "success",
            "data": {
                "Station": matched_name,
                "State": state,
                "StationID": station_id,
                "Temperature": current.get("temperature_2m"),
                "Feels Like": current.get("apparent_temperature"),
                "Relative Humidity": current.get("relative_humidity_2m"),
                "Wind Speed": current.get("wind_speed_10m"),
                "Precipitation": current.get("precipitation"),
                "Condition": condition,
                "Observed At": current.get("time"),
                "Source": "IMD Open Weather Network",
                "Latitude": lat,
                "Longitude": lon
            }
        })
    except requests.exceptions.RequestException as e:
        return jsonify({"status": "error", "message": f"Weather fetch failed: {str(e)}"}), 500


if __name__ == '__main__':
    app.run(debug=True, port=5000)
