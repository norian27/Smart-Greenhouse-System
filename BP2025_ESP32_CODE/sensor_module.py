"""
Sensor reading and control logic for the microcontroller.

This module's code is based on what type of attachments the microcontroller possesses.

It provides functions for reading sensor data (temperature, humidity, soil moisture),
handling water flow measurement, and controlling relays for environmental systems.
"""

from machine import Pin, ADC
import time
import mqtt_module as mqtt
import config_module as config
import dht
import uasyncio as asyncio
import json
from utils_module import log
#Hardware Setup
FLOW_SENSOR_PIN = 21
RELAY_PIN = 22


flow_pin = Pin(FLOW_SENSOR_PIN, Pin.IN)
relay = Pin(RELAY_PIN, Pin.OUT)
relay.value(1)

#Constants
MAX_WATER_LEVEL = 20000 #Approx. 2 liters
pulses_per_liter = 9844

#State variables
pulses = 0
last_time = 0

def pulse_callback(pin):
    """
    Callback function to count pulses from the flow sensor.

    Parameters:
        pin (Pin): The GPIO pin object triggering the callback.
    """
    global pulses, last_time
    now = time.ticks_ms()
    if time.ticks_diff(now, last_time) > 10:  # Debounce
        pulses += 1
        last_time = now

# Attach interrupt to flow sensor pin
flow_pin.irq(trigger=Pin.IRQ_RISING, handler=pulse_callback)

def read_water_flow():
    """
    Reads and resets the counted water flow pulses.

    Returns:
        int: The number of pulses detected since the last reading.
    """
    global pulses
    total = pulses
    pulses = 0
    return total


def control_relay(turn_on):
    """
    Controls the relay to activate or deactivate the environmental system.

    Parameters:
        turn_on (bool): True to activate, False to deactivate.
    """
    relay.value(0 if turn_on else 1)
    config.edit_config('config.json', {'sensor': {'allow_data_flow': turn_on}})


def get_sensor_data(pulses_used=0):
    """
    Generates water flow sensor data based on pulse count.

    Parameters:
        pulses_used (int): The number of pulses used for calculating water flow.

    Returns:
        list: A list containing a dictionary of water flow measurements.
    """
    readings = []
    try:
        liters_used = pulses_used / pulses_per_liter
                    
        cfg = config.load_config('config.json')
        current_level = cfg['sensor']['current_water_level']
        
        pulses_remaining = max(0, MAX_WATER_LEVEL - current_level)
        liters_remaining = pulses_remaining / pulses_per_liter
        percent_remaining = max(0, int((pulses_remaining / MAX_WATER_LEVEL) * 100))

        readings.append({
            'type': 'water_flow',
            'pulses': pulses_used,
            'status': 'ongoing',
            'liters_used': round(liters_used, 3),
            'liters_remaining': round(liters_remaining, 3),
            'percent_remaining': percent_remaining
        })
        
    except Exception as e:
        log(f"Error reading Water Flow sensor: {e}")
    return readings


async def monitor_during_flow(unique_id, topic):
    """
    Monitors the water flow during system activation and auto-deactivates if maximum level is reached.

    Parameters:
        unique_id (str): Unique identifier of the device.
        topic (str): MQTT topic for publishing auto-deactivation events.
    """

    log("Starting async flow monitor during activation.")
    
    while True:
        cfg = config.load_config('config.json')

        if not cfg['sensor'].get('allow_data_flow', False):
            break


        if cfg['sensor']['current_water_level'] >= MAX_WATER_LEVEL:
            log("[AUTO-CUTOFF] Max water level reached! Auto-deactivating.")
            control_relay(False)

            total_pulses = read_water_flow()
            cfg['sensor']['current_water_level'] += total_pulses
            config.edit_config('config.json', cfg)

            flow_data = get_sensor_data(total_pulses)
            payload = {
                'unique_identifier': unique_id,
                'status': 'refused',
                'reason': 'Auto-stop during flow',
                'data': flow_data
            }
            mqtt.client.publish(topic, json.dumps(payload).encode())
            break

        await asyncio.sleep(3)


def control_env_system(command):
    """
    Processes control commands to activate, deactivate, or reset the environmental system.

    Parameters:
        command (dict): The control command received.

    Returns:
        dict or None: A response payload for MQTT publishing, or None if no response needed.
    """
    try:
        action = command.get('action')
        unique_id = config.cfg['sensor']['unique_id']
        topic = config.cfg['mqtt']['protected_topics']['control'] + '/' + unique_id
        
        if action == 'activate':
            cfg = config.load_config('config.json')
            current_level = cfg['sensor'].get('current_water_level', 0)
            
            if current_level >= MAX_WATER_LEVEL:
                log("[WARNING] Water level exceeded. Activation refused.")
                return {
                    'topic': topic,
                    'payload': {
                        'unique_identifier': unique_id,
                        'status': 'refused',
                    }
                }
            log("Activating sprinkler relay")
            control_relay(True)
            confirmation_payload = {
                'unique_identifier': unique_id,
                'status': 'started',
            }
            mqtt.client.publish(topic, json.dumps(confirmation_payload).encode())
            asyncio.create_task(monitor_during_flow(unique_id, topic))

            return None
            
        elif action == 'deactivate':
            log("Deactivating sprinkler relay")
            
            allow_update = config.cfg['sensor'].get('allow_data_flow', False)

            control_relay(False)
            
            total_pulses = read_water_flow()
            
            if allow_update:
                cfg = config.load_config('config.json')
                cfg['sensor']['current_water_level'] += total_pulses
                config.edit_config('config.json', cfg)

            flow_data = get_sensor_data(total_pulses)
            final_data = []
            for reading in flow_data:
                if reading['type'] == 'water_flow':
                    final_data.append({
                        'type': 'water_flow',
                        'liters_remaining': reading['liters_remaining'],
                        'percent_remaining': reading['percent_remaining']
                    })
            return {
                'topic': topic,
                'payload': {
                    'unique_identifier': unique_id,
                    'status': 'completed',
                    'data': final_data
                }
            }
        elif action == 'reset':
            log("Reseting sprinkler to full")
            cfg = config.load_config('config.json')
            cfg['sensor']['current_water_level'] = 0
            config.edit_config('config.json',cfg)
            
            return None
        else:
            log(f"Unknown action received: {action}")
            return None
    except Exception as e:
        log(f"Error processing environment control system command: {e}")
        return None
    