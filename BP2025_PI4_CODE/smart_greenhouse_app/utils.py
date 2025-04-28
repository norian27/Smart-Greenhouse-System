import requests

def fetch_location_via_ip():
    try:
        response = requests.get('https://ipinfo.io/json?token=69ed127e05c258')
        data = response.json()

        if 'loc' in data:
            lat, lon = data['loc'].split(',')
            return float(lat), float(lon)
        else:
            error_message = data.get('error', 'No location data available.')
            print(f"Error: {error_message}")
            return None, None
    except Exception as e:
        print(f"An error occurred: {str(e)}")
        return None, None
