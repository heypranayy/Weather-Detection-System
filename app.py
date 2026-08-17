from flask import Flask, render_template, jsonify, request
import requests

# Import the massive dictionary from your new stations.py file
from stations import STATIONS

app = Flask(__name__)

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/api/stations', methods=['GET'])
def get_stations():
    # Send the imported dictionary to the frontend
    return jsonify(STATIONS)

@app.route('/api/weather', methods=['GET'])
def get_weather():
    station_id = request.args.get('station_id')
    
    if not station_id:
        return jsonify({"status": "error", "message": "No station ID provided"}), 400

    imd_url = f"https://api.imd.gov.in/api/v1/current_wx?id={station_id}"
    
    # Adding headers is good practice to ensure the IMD server doesn't block the request
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'
    }
    
    try:
        response = requests.get(imd_url, headers=headers, timeout=10)
        response.raise_for_status() 
        data = response.json()
        
        return jsonify({
            "status": "success",
            "data": data
        })
        
    except requests.exceptions.RequestException as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)