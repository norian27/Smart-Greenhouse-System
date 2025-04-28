Smart Greenhouse Project
========================

This is a Django-based system for monitoring and controlling greenhouse operations with sensor data, system control, WebSocket updates, and MQTT communication with microcontrollers.

Requirements
------------

- Python 3.9+
- Redis Server (for Celery and WebSockets backend)
- Mosquitto MQTT Broker (for device communication)

Python Dependencies
--------------------

Install via pip:

    pip install Django==4.2.10
    pip install channels
    pip install channels_redis
    pip install celery
    pip install paho-mqtt
    pip install django-extensions
    pip install widget-tweaks
    pip install redis

Setup Instructions
-------------------

1. Install and run Redis

    sudo apt update
    sudo apt install redis
    sudo systemctl start redis

2. Install and run Mosquitto

    sudo apt update
    sudo apt install mosquitto mosquitto-clients
    sudo systemctl enable mosquitto
    sudo systemctl start mosquitto

3. Apply database migrations

    python manage.py migrate

4. Start the Django server (since the app uses WebSockets I'm using uvicorn)
    
    uvicorn smart_greenhouse.asgi:application --host 0.0.0.0 --port 8001

5. Start the MQTT script for handling communication

    python mqtt_communication.py

6. Start the Celery worker

    celery -A smart_greenhouse worker --loglevel=info

7. Start the Celery Beat scheduler

    celery -A smart_greenhouse beat --loglevel=info

8. Access the application

Open http://localhost:8001 in your browser.

9. Create a Greenhouse using the UI.

10. Once you run the code for microcontroller, you should at first see a new device in 'Pending Registrations' tab There confirm the registration (if you don't, you might have to restart the microcontroller),
choose if it's Sensor Unit or Enviromental System and confirm.

11. You will then be able to control the system in the greenhouse or you'll be able to see the sensor data - by editing sensor unit, you are able to set thresholds used for Alerts.

Important Notes
---------------

- The project uses WebSockets heavily, make sure you serve it using an ASGI server (such as `daphne` or `uvicorn`).
- Sensor data and system control are handled through MQTT messages.
- Ensure the device running this project can act as a Wi-Fi hotspot. Sensor units (microcontrollers) will connect to this hotspot for MQTT communication. 
Whatever set up you do for your device, the details (Network name, password) have to be set up on the microcontrollers as well.
- 'data/sensor_data.csv' contains updated sensor data
