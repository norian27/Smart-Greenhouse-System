"""
Main for running sensor operations or environmental system operations on the microcontroller.

This script initializes the device configuration, generates a unique identifier if needed,
and runs the main loop to send sensor data and handle MQTT communication.
"""
import config_module as config
import sensor_module as sensor
import utils_module as utils
from network_module import connect_to_wifi
from mqtt_module import connect_to_mqtt, send_data, request_settings
from utils_module import log
import time
import os

# Last modification time of the configuration file
last_mod_time = os.stat('config.json')[8]



def run_sensor_operations():
    """
    Handles the main loop for collecting and sending sensor data via MQTT.

    Continuously sends sensor data based on the configured data frequency,
    checks for incoming MQTT messages, and sends sensor readings to the broker.

    Raises:
        Exception: If an error occurs while checking MQTT messages.
    """
    connect_to_wifi()
    mqtt_client = connect_to_mqtt()
    unit_type = config.cfg['sensor']['unit_type']

    last_data_time = time.time()
    last_settings_request_time = time.time()
    log("Running sensor operations.")
    
    while True:
        data_frequency = config.cfg['sensor']['data_frequency']
        allow_data_flow = config.cfg['sensor']['allow_data_flow']
        current_time = time.time()
        
        if unit_type == "sensor_unit" or allow_data_flow:
            
            if config.cfg['sensor']['is_registered'] and (current_time - last_data_time) >= data_frequency:
                send_data(mqtt_client, config.cfg['sensor']['unique_id'])
                last_data_time = current_time
                log("Sent sensor data.")           
        try:
            mqtt_client.check_msg()
        except Exception as e:
            log(f"Error checking messages: {e}")

        time.sleep(0.1)


def main():
    """
    Main initialization function.

    Generates a unique identifier for the device, updates the configuration file,
    and starts the main loop.
    """
    uid = utils.get_unique_identifier()

    config.load_config('config.json')
    config.edit_config('config.json', {'sensor': {'unique_id': uid}})
    
    config.load_config('config.json')

    run_sensor_operations()