"""
MQTT communication module for the microcontroller.

This module manages connecting to the MQTT broker, subscribing to topics,
handling incoming messages, and publishing sensor data and settings.
"""
import config_module as config
import sensor_module as sensor
from utils_module import log, get_unique_identifier
from simple2 import MQTTClient
import json
import gc
import ssl


def read_data(file_name: str):
    """
    Reads the contents of a file.

    Parameters:
        file_name (str): The path to the file to be read.

    Returns:
        bytes: The contents of the file.

    Raises:
        Exception: If the file cannot be opened or read.
    """
    try:
        with open(file_name, 'rb') as f:
            data = f.read()
            if not data:
                raise Exception('No key data')
            return data
    except OSError:
        raise Exception('Problems when loading a file: %s' % file_name)


def sub_cb(topic, msg, retained, duplicate):
    """
    Callback function for handling received MQTT messages.

    Parameters:
        topic (bytes): The topic the message was published on.
        msg (bytes): The message payload.
        retained (bool): True if the message is retained.
        duplicate (bool): True if the message is a duplicate.

    Processes settings updates, registration confirmations, or control commands.
    """
    log(f"Received message on topic: {topic.decode()}, Payload: {msg.decode()}, Retained: {retained}, Duplicate: {duplicate}")

    if duplicate:
        log(f"Duplicate message received on {topic.decode()}")
    if retained:
        log(f"This is a retained message.")
    
    log(f"[DEBUG] Received message on topic: {topic.decode()}, Payload: {msg.decode()}")
    topic = topic.decode()
    try:
        if 'settings/' in topic and config.cfg['sensor']['unique_id'] in topic:
            settings = json.loads(msg.decode())
            log(f"Received settings: {settings}")

            data_frequency = settings.get('data_frequency', 10)
            log(f"[DEBUG] Current data frequency: {config.cfg['sensor'].get('data_frequency', 'not set')}")

            config.edit_config('config.json', {'sensor': {'data_frequency': data_frequency}})

            log(f"Updated data frequency to {data_frequency} seconds.")
            log(f"[DEBUG] New data frequency: {config.cfg['sensor']['data_frequency']}")

        elif topic.endswith(f'response/{config.cfg["sensor"]["unique_id"]}'):
            response = json.loads(msg.decode())
            if not response.get('registered', False):
                log("Registering sensor.")
                client.publish(f'sensor/register/{config.cfg["sensor"]["unique_id"]}', json.dumps({'unique_identifier': config.cfg["sensor"]["unique_id"]}))
            else:
                config_data = config.load_config('config.json')
                config_data['sensor']['is_registered'] = True
                config.edit_config('config.json', config_data)
                log("Sensor is already registered.")
                
        elif topic.endswith(f'system/control/command/{config.cfg["sensor"]["unique_id"]}'):
            try:
                command = json.loads(msg)
                response = sensor.control_env_system(command)
                if response:
                    client.publish(response['topic'], json.dumps(response['payload']).encode())
            except Exception as e:
                log(f"[ERROR] Error processing control command: {e}")
        

    except Exception as e:
        log(f"[ERROR] Error in sub_cb at {topic}: {e}")

def load_ssl_params():
    """
    Loads SSL/TLS certificates required for a secure MQTT connection.

    Returns:
        dict: A dictionary containing SSL parameters (key, cert, CA certificate).

    Raises:
        Exception: If reading certificate files fails.
    """
    try:
        log("Attempting to read key data")
        key_data = read_data(config.cfg['certificates']['client']['key'])
        log("Key data read successfully")

        log("Attempting to read cert data")
        cert_data = read_data(config.cfg['certificates']['client']['certificate'])
        log("Cert data read successfully")

        log("Attempting to read CA cert data")
        ca_cert_data = read_data(config.cfg['certificates']['ca'])
        log("CA cert data read successfully")
    except Exception as e:
        log(f"Failed to read key/cert data: {e}")
        raise
    return {
        'cert': cert_data,
        'key': key_data,
        'ca_certs': ca_cert_data,
    }


def connect_to_mqtt():
    """
    Connects to the MQTT broker using SSL/TLS authentication.

    Subscribes to required topics after a successful connection.
    
    Returns:
        MQTTClient: The connected MQTT client instance.

    Raises:
        Exception: If connection to all brokers fails.
    """
    global client
    unique_id = config.cfg['sensor']['unique_id']
    unit_type = config.cfg['sensor']['unit_type']
    gc.collect()

    for broker_ip in config.cfg['network']['mqtt_brokers']:
        log(f"Connecting to broker: {broker_ip}")
        try:
            client = MQTTClient(client_id=unique_id,
                                server=broker_ip,
                                port=config.cfg['network']['mqtt_port'],
                                user='smart_greenhouse',
                                password='radegast1',
                                ssl=True,
                                ssl_params=load_ssl_params())
            client.set_callback(sub_cb)
            log(f"Connecting to MQTT broker at {broker_ip}...")
            client.connect()
            log("Connected to MQTT broker.")
            
            # Subscribe to required topics
            response_topic = f'sensor/check/response/{unique_id}'
            client.subscribe(response_topic)
            log(f"Subscribed to {response_topic}")
            client.subscribe(f'{config.cfg["mqtt"]["protected_topics"]["settings_response"]}/{unique_id}')
            log(f"Subscribed to settings response for {unique_id}")
            log(f"Subscribed to {response_topic}")
            check_topic = f'sensor/check/{unique_id}'
            client.publish(check_topic, '{}')
            log(f"Published check to {check_topic}")
            if unit_type == 'env_system':
                control_topic = f'system/control/command/{unique_id}'
                client.subscribe(control_topic)
                log(f"Subscribed to environment control topic {control_topic}")
            return client
        except OSError as e:
                   log(f"Failed to connect to MQTT broker at {broker_ip} due to OSError: {e}")
        except Exception as e:
            log(f"Failed to connect to MQTT broker at {broker_ip} due to an unexpected error: {e}")
    raise Exception("Failed to connect to any MQTT broker.")




def request_settings():
    """
    Sends a settings request message to the MQTT broker.

    Publishes an empty JSON payload requesting updated settings from the backend.
    """
    client.publish(f'{config.cfg["mqtt"]["protected_topics"]["settings_request"]}/{config.cfg["sensor"]["unique_id"]}', '{}') 
    log("Requested settings.")

def send_data(client, unique_id):
    """
    Sends sensor or environmental system data to the MQTT broker.

    Parameters:
        client (MQTTClient): The connected MQTT client instance.
        unique_id (str): The unique identifier of the sending device.

    Raises:
        Exception: If an error occurs while sending data.
    """

    if not config.cfg['sensor']['is_registered']:
        log('Sensor is not registered. Data not sent.')
        return

    try:
        unit_type = config.cfg['sensor']['unit_type']
        readings = sensor.get_sensor_data()
        
        if unit_type == 'env_system':
            payload = {
                'unique_identifier': unique_id,
                'data': readings,
            }
            topic = config.cfg['mqtt']['protected_topics']['control'] + '/' + unique_id
        else:
            payload = {
                'unique_identifier': unique_id,
                'data': readings
            }
            topic = config.cfg['mqtt']['protected_topics']['data'] + '/' + unique_id
            
        client.publish(topic, json.dumps(payload).encode())
        log('Data published: ' + json.dumps(payload) + ' on topic ' + topic)

    except Exception as e:
        log(f"Error sending sensor data: {e}")