from flask import Flask, render_template, jsonify, request
import requests

app = Flask(__name__)

# WMO Weather Codes mapping to condition descriptions and emojis
WMO_CODES = {
    0: ("Clear Sky", "☀️"),
    1: ("Mainly Clear", "🌤️"),
    2: ("Partly Cloudy", "⛅"),
    3: ("Overcast", "☁️"),
    45: ("Foggy", "🌫️"),
    48: ("Rime Fog", "🌫️"),
    51: ("Light Drizzle", "🌦️"),
    53: ("Moderate Drizzle", "🌦️"),
    55: ("Dense Drizzle", "🌧️"),
    56: ("Freezing Drizzle", "🌧️❄️"),
    57: ("Dense Freezing Drizzle", "🌧️❄️"),
    61: ("Slight Rain", "🌧️"),
    63: ("Moderate Rain", "🌧️"),
    65: ("Heavy Rain", "🌧️"),
    66: ("Freezing Rain", "🌧️❄️"),
    67: ("Heavy Freezing Rain", "🌧️❄️"),
    71: ("Slight Snow", "🌨️"),
    73: ("Moderate Snow", "🌨️"),
    75: ("Heavy Snow", "❄️"),
    77: ("Snow Grains", "❄️"),
    80: ("Rain Showers", "🌦️"),
    81: ("Moderate Showers", "🌧️"),
    82: ("Violent Showers", "⛈️"),
    85: ("Snow Showers", "🌨️"),
    86: ("Heavy Snow Showers", "❄️"),
    95: ("Thunderstorm", "⛈️"),
    96: ("Thunderstorm / Hail", "⛈️🌩️"),
    99: ("Severe Storm / Hail", "⛈️🌩️")
}


@app.route('/')
def home():
    return render_template('index.html')


@app.route('/api/search', methods=['GET'])
def search_places():
    query = request.args.get('q', '').strip()
    if not query:
        return jsonify({"status": "success", "results": []})
    
    try:
        geocode_url = f"https://geocoding-api.open-meteo.com/v1/search?name={requests.utils.quote(query)}&count=8"
        response = requests.get(geocode_url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            results = []
            for item in data.get('results', []):
                parts = [item.get('name', '')]
                if item.get('admin2') and item.get('admin2') not in parts:
                    parts.append(item.get('admin2'))
                if item.get('admin1') and item.get('admin1') not in parts:
                    parts.append(item.get('admin1'))
                if item.get('country') and item.get('country') not in parts:
                    parts.append(item.get('country'))
                
                results.append({
                    "name": item.get('name'),
                    "display": ", ".join(parts),
                    "lat": item.get('latitude'),
                    "lon": item.get('longitude'),
                    "country": item.get('country')
                })
            return jsonify({"status": "success", "results": results})
        return jsonify({"status": "success", "results": []})
    except Exception:
        return jsonify({"status": "success", "results": []})


@app.route('/api/weather', methods=['GET'])
def get_weather():
    city_name = request.args.get('city') or request.args.get('station') or request.args.get('q')
    lat_arg = request.args.get('lat')
    lon_arg = request.args.get('lon')
    
    if not city_name and (not lat_arg or not lon_arg):
        return jsonify({"status": "error", "message": "No city or location provided"}), 400

    try:
        detailed_location = ""
        matched_city = ""
        district = ""
        state = ""
        country = ""
        lat = None
        lon = None

        if lat_arg and lon_arg:
            lat = float(lat_arg)
            lon = float(lon_arg)
            detailed_location = city_name or f"{lat}, {lon}"
        else:
            # Geocoding via Open-Meteo API
            geocode_url = f"https://geocoding-api.open-meteo.com/v1/search?name={requests.utils.quote(city_name)}&count=1"
            geo_response = requests.get(geocode_url, timeout=10)
            geo_response.raise_for_status()
            geo_data = geo_response.json()
            
            if not geo_data.get('results'):
                return jsonify({"status": "error", "message": f"Location '{city_name}' not found. Please check spelling."}), 404
                
            location = geo_data['results'][0]
            lat = location['latitude']
            lon = location['longitude']
            
            matched_city = location.get('name', '')
            district = location.get('admin2', '')
            state = location.get('admin1', '')
            country = location.get('country', '')

            # Build clean location hierarchy
            loc_parts = []
            if matched_city: loc_parts.append(matched_city)
            if district and district not in loc_parts: loc_parts.append(district)
            if state and state not in loc_parts: loc_parts.append(state)
            if country and country not in loc_parts: loc_parts.append(country)
                
            detailed_location = ", ".join(loc_parts)
        
        # Step 2: Fetch Telemetry from Open-Meteo
        variables = "temperature_2m,relative_humidity_2m,apparent_temperature,is_day,precipitation,snowfall,weather_code,cloud_cover,surface_pressure,wind_speed_10m,wind_gusts_10m"
        weather_url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current={variables}&timezone=auto"
        
        weather_response = requests.get(weather_url, timeout=10)
        weather_response.raise_for_status()
        weather_data = weather_response.json()
        
        current = weather_data.get('current', {})
        units = weather_data.get('current_units', {})
        
        weather_code = current.get('weather_code', 0)
        condition_text, condition_icon = WMO_CODES.get(weather_code, ("Unknown", "❓"))
        
        is_day = current.get('is_day', 1)
        if not is_day:
            if weather_code == 0: condition_icon = "🌙"
            elif weather_code in [1, 2]: condition_icon = "☁️🌙"

        # Determine Weather Theme for Dynamic Dark Pastel Background & Particle Effects
        if weather_code in [95, 96, 99]:
            theme = "stormy"
        elif (51 <= weather_code <= 67) or (80 <= weather_code <= 82) or (current.get('precipitation', 0) > 0):
            theme = "rainy"
        elif (71 <= weather_code <= 77) or (85 <= weather_code <= 86) or (current.get('snowfall', 0) > 0):
            theme = "snowy"
        elif weather_code in [45, 48]:
            theme = "foggy"
        elif weather_code in [2, 3]:
            theme = "cloudy"
        else:
            theme = "clear-day" if is_day else "clear-night"

        # Rain Calculation
        precip_amount = current.get('precipitation', 0)
        if precip_amount > 0 or theme == "rainy":
            raining_status = f"Yes ({precip_amount} {units.get('precipitation', 'mm')})"
        else:
            raining_status = "No (0 mm)"

        # Snow Calculation
        snowfall_amount = current.get('snowfall', 0)
        if snowfall_amount > 0 or theme == "snowy":
            snowing_status = f"Yes ({snowfall_amount} {units.get('snowfall', 'cm')})"
        else:
            snowing_status = "No (0 cm)"

        # Extreme Alert Thresholds
        wind_speed = current.get('wind_speed_10m', 0)
        extreme_alert = ""
        if wind_speed >= 118:
            extreme_alert = "🚨 EXTREME DANGER: CYCLONE / HURRICANE FORCE WINDS 🚨"
        elif wind_speed >= 88:
            extreme_alert = "⚠️ SEVERE STORM WARNING: GALE FORCE WINDS ⚠️"
        elif weather_code in [82, 95, 96, 99]:
            extreme_alert = "🌩️ ALERT: SEVERE THUNDERSTORM / HAIL ACTIVITY 🌩️"

        payload = {
            "city": detailed_location,
            "name": matched_city or city_name,
            "district": district,
            "state": state,
            "country": country,
            "latitude": lat,
            "longitude": lon,
            "condition": condition_text,
            "icon": condition_icon,
            "theme": theme,
            "extreme_alert": extreme_alert,
            "temperature": f"{current.get('temperature_2m', '--')}",
            "temp_unit": f"{units.get('temperature_2m', '°C')}",
            "feels_like": f"{current.get('apparent_temperature', '--')} {units.get('apparent_temperature', '°C')}",
            "humidity": f"{current.get('relative_humidity_2m', '--')} {units.get('relative_humidity_2m', '%')}",
            "raining_status": raining_status,
            "snowing_status": snowing_status,
            "cloud_cover": f"{current.get('cloud_cover', '--')} {units.get('cloud_cover', '%')}",
            "wind_speed": f"{wind_speed} {units.get('wind_speed_10m', 'km/h')}",
            "wind_gusts": f"{current.get('wind_gusts_10m', '--')} {units.get('wind_gusts_10m', 'km/h')}",
            "surface_pressure": f"{current.get('surface_pressure', '--')} {units.get('surface_pressure', 'hPa')}"
        }
        
        return jsonify({"status": "success", "data": payload})
        
    except requests.exceptions.RequestException as e:
        return jsonify({"status": "error", "message": f"Telemetry server connection error: {str(e)}"}), 500


if __name__ == '__main__':
    app.run(debug=True, port=5000)
