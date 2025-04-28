Smart Greenhouse Microcontroller Code
=======================================

This is a MicroPython code for the sensor units and environmental systems used in the Smart Greenhouse bachelor project. 
The microcontrollers connect over Wi-Fi and communicate securely via MQTT.

Requirements
------------

- Microcontroller capable of running MicroPython and supporting Wi-Fi (e.g., ESP32, Raspberry Pi Pico W)
- MicroPython firmware installed
- MQTT broker address and Wi-Fi credentials configured
- Ability to use TLS certificates for secure MQTT communication

MicroPython Dependencies
-------------------------

This code is designed to work with standard MicroPython modules and includes custom modules like:

- mqtt_module.py
- network_module.py
- sensor_module.py
- utils_module.py
- TLS support (ussl.py)
- Lightweight MQTT clients (simple.py, simple2.py, robust.py)

Setup Instructions
-------------------

1. Flash MicroPython firmware to your microcontroller (if not already installed).

2. Prepare the code:
    - Upload all `.py` files to the microcontroller using a tool like `ampy`, `rshell`, `Thonny`.
    - Upload the certificate files:
        - ca.crt
        - client.crt
        - client.key
    - Upload `config.json` and configure:
        - Wi-Fi SSID and password
        - MQTT broker address and port
        - TLS settings (client certificate and key)

3. Boot sequence:
    - `boot.py` will automatically run at startup.
    - `main.py` will initialize Wi-Fi, connect to the broker, and start operation loops.

4. Configure microcontroller settings:
    - Ensure the Wi-Fi credentials match the Wi-Fi hotspot provided by the main server running the Django application (e.g., Raspberry Pi 4).
    - Ensure the MQTT broker address is reachable by the the microcontroller.
    - Set device unique identifiers (this should be set automatically on start up) and sensor settings properly in `config.json`.

Important Notes
---------------

- Wi-Fi Connectivity:  
  The microcontroller must connect to the Wi-Fi hotspot provided by the server device (e.g., Raspberry Pi 4).  
  Network name (SSID) and password must be correctly set in `config.json`.

- MQTT Security:  
  Communication uses secure MQTT over TLS.  
  Ensure the certificates (`ca.crt`, `client.crt`, `client.key`) are valid and match the server configuration.

- Registration:  
  When the microcontroller first connects, it will appear under "Pending Registrations" on the server.  
  Registration must be confirmed manually through the server’s UI. (per README.TXT in the Django project folder)
