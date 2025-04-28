"""
MQTT Interaction script for smart_greenhouse.

This script sets up MQTT client connections and handles incoming MQTT messages related to sensor data, environmental system control, registration,
and settings adjustments. It uses the paho-mqtt client library to interact with an MQTT broker and processes messages
according to their topics.

This script is set up to run as a standalone component that interacts with the Django models to perform necessary actions
based on the data received from MQTT topics.

Dependencies:
- paho-mqtt: For MQTT client functionalities.
- Django: For ORM operations to interact with the database.
- SSL: For secured MQTT connections.
"""

import logging, sys


for h in logging.root.handlers[:]:
    logging.root.removeHandler(h)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    stream=sys.stdout,
    force=True
)

logger = logging.getLogger("smart_greenhouse")
logger.setLevel(logging.INFO)

handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)-8s %(name)s: %(message)s"))
handler.setLevel(logging.INFO)
logger.addHandler(handler)

logger.propagate=False

import os
import csv
import time
import signal
import django
import json
import ssl
import paho.mqtt.client as mqtt
import paho.mqtt.publish as publish
from django.utils.timezone import now
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db.models.signals import post_save
from django.dispatch import receiver
from threading import Timer




os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'smart_greenhouse.settings')
django.setup()




from smart_greenhouse_app.models import EnvironmentalSystem, SensorUnit, PendingSensorRegistration, Greenhouse, sanitize_string, WindowControlSystem

# MQTT Broker details
MQTT_HOST = '10.42.0.1'
MQTT_PORT = 8883  # TLS port for secure communication
SENSOR_DATA_TOPIC = 'sensor/data/#'
SENSOR_REGISTER_TOPIC = 'sensor/register/#'
SENSOR_SETTINGS_TOPIC = 'sensor/settings/request/#'
SENSOR_CHECK_TOPIC = 'sensor/check/#'
SYSTEM_CONTROL_COMMAND = 'system/control/command/#'
SYSTEM_CONTROL_RESPONSE = 'system/control/response/#'

ca_path = "/etc/mosquitto/certs/ca.crt"
certfile_path = "/etc/mosquitto/certs/client.crt"
keyfile_path = "/etc/mosquitto/certs/client.key"




client = mqtt.Client()


client.tls_set(ca_certs=ca_path, certfile=certfile_path, keyfile=keyfile_path, tls_version=ssl.PROTOCOL_TLSv1_2)
client.tls_insecure_set(False)
client.username_pw_set('smart_greenhouse', 'radegast1')





pending_confirmations = {}


def graceful_shutdown(signum, frame):
    """
    Handles graceful shutdown of the MQTT client on receiving termination signals.

    Parameters:
        signum (int): The signal number.
        frame: Current stack frame.
    """
    logger.info("Shutting down MQTT client...")
    client.loop_stop()
    client.disconnect()
    logger.info("MQTT client disconnected.")
    exit(0)

def on_connect(client, userdata, flags, rc):
    """
    Handles the event triggered upon connecting with the MQTT broker.
    Subscribes to necessary topics to receive sensor data and other information.

    Parameters:
        client (mqtt.Client): The client instance for this callback.
        userdata: The private user data as set in Client() or user_data_set().
        flags: Response flags sent by the broker.
        rc (int): The connection result.
    """
    logger.info(f"Connected with result code {rc}")
    client.subscribe([
        (SENSOR_DATA_TOPIC, 0),
        (SENSOR_REGISTER_TOPIC, 0),
        (SENSOR_SETTINGS_TOPIC, 0),
        (SENSOR_CHECK_TOPIC, 0),
        (SYSTEM_CONTROL_COMMAND, 0),
        (SYSTEM_CONTROL_RESPONSE,0),
    ])
def on_message(client, userdata, msg):
    """
    Callback for when a PUBLISH message is received from the server.

    Parameters:
        client (mqtt.Client): The client instance for this callback.
        userdata: The private user data as set in Client() or user_data_set().
        msg (MQTTMessage): An instance of MQTTMessage, which is a class with members topic, payload, qos, retain.
    """
    logger.info(f"Message received on topic {msg.topic}")
    try:
        payload = json.loads(msg.payload.decode())

        if "check/response" in msg.topic:
            logger.debug(f"Ignoring response message on topic: {msg.topic}")
            return

        if msg.topic.startswith('sensor/data'):
            unique_id = payload.get('unique_identifier')
            sensor_data = payload.get('data')

            if unique_id and sensor_data:
                handle_sensor_data(unique_id, sensor_data)
            else:
                logger.error("Unique ID or sensor data missing in payload.")
                return
        
        if 'system/control/response' in msg.topic:
            unique_id = payload.get('unique_identifier')
            handle_environmental_system(unique_id, payload)
            return

        topic_parts = msg.topic.split('/')
        if topic_parts[1] == 'check' and len(topic_parts) > 2:
            handle_check_request(topic_parts[2], client)
        elif topic_parts[1] == 'register' and len(topic_parts) > 2:
            handle_registration(topic_parts[2])
        elif topic_parts[1] == 'settings' and len(topic_parts) > 2:
            handle_settings_request(topic_parts[3], client)
        elif topic_parts[1] == 'control' or topic_parts[1] == 'data' and len(topic_parts) > 2:
            pass
        else:
            logger.warning(f"Unhandled message type in topic: {msg.topic}")
    except Exception as e:
        logger.exception(f"Error handling message: {e}")

def handle_environmental_system(unique_id,data):
    """
    Handles updates to an environmental system based on received MQTT control responses.

    Parameters:
        unique_id (str): The unique identifier of the environmental system.
        data (dict): The response payload containing status information.
    """
    try:
        logger.debug(f"Payload for environmental system: {data}")
        env_system = EnvironmentalSystem.objects.get(unique_identifier=unique_id)

        if data.get('status') == 'started':
            if unique_id in pending_confirmations:
                pending_confirmations[unique_id].cancel()
                del pending_confirmations[unique_id]
            env_system.status = 'started'
            env_system.save(update_fields=['status'])
            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.group_send)(
                f'env_system_{unique_id}',
                {
                    'type': 'status_update',
                    'system_id': str(unique_id),
                    'is_active': env_system.is_active,
                    'status': env_system.status,
                }
            )
        
        if data.get('status') in ['completed','refused']:
            env_system.status = data.get('status')
            env_system.is_active = False
            env_system.data = json.dumps(data)
            env_system.save(update_fields=['is_active', 'data', 'status'])    
            logger.info(f"Updated environmental system {unique_id} as completed.")
            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.group_send)(
                f'env_system_{unique_id}',
                {
                    'type': 'status_update',
                    'system_id': str(unique_id),
                    'is_active': env_system.is_active,
                    'status': env_system.status,
                }
            )

    except EnvironmentalSystem.DoesNotExist:
        logger.warning(f"No environmental system found with ID: {unique_id}")
    except Exception as e:
        logger.exception(f"Error updating environmental system status for {unique_id}: {e}")        

def publish_control_command(env_system, action):
    """
    Publishes a control command to an environmental system via MQTT.

    Parameters:
        env_system (EnvironmentalSystem): The environmental system instance.
        action (str): The action to perform ('activate', 'deactivate', or 'reset').
    """
    env_system.refresh_from_db()
    angle = None
    if env_system.env_type == 'Window':
        try:
            env_system = WindowControlSystem.objects.get(pk=env_system.pk)
            angle = env_system.current_angle
        except WindowControlSystem.DoesNotExist:
            logger.error(f"WindowControlSystem not found for ID {env_system.pk}")
    message = {'unique_identifier':env_system.unique_identifier,
                           'action':action}
    


    if hasattr(env_system, 'windowcontrolsystem'):
        angle = env_system.windowcontrolsystem.current_angle
    
    if angle is not None:
        message['angle'] = angle
        logger.debug(f"Included angle: {angle}")
    else:
        logger.debug("No angle included")
    
    topic = f'system/control/command/{env_system.unique_identifier}'

    try:
        publish.single(
            topic,
            payload=json.dumps(message),
            qos=1,
            hostname=MQTT_HOST,
            port=MQTT_PORT,
            tls={'ca_certs': ca_path, 'certfile': certfile_path, 'keyfile': keyfile_path, 'tls_version': ssl.PROTOCOL_TLSv1_2},
            auth={'username': 'smart_greenhouse', 'password': 'radegast1'},
            retain=False
        )

        logger.info(f"Published MQTT message for {env_system.unique_identifier} to {action}")
        logger.debug(f"Message payload: {message}")

        env_system.status = 'waiting'
        env_system.save(update_fields=['status'])
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f'env_system_{env_system.unique_identifier}',
            {
                'type': 'status_update',
                'system_id': str(env_system.unique_identifier),
                'is_active': env_system.is_active,
                'status': env_system.status,
            }
        )

        def timeout_check():
            #Function for checkińg if Envrionmental System unit is connected to the system.
            try:
                system = EnvironmentalSystem.objects.get(pk=env_system.pk)
                if system.status == 'waiting':
                    system.status = 'unreachable'
                    system.is_active = False
                    system.save(update_fields=['status', 'is_active'])
                    logger.warning(f"[TIMEOUT] No confirmation from {system.name}. Marked as unreachable.")
                    channel_layer = get_channel_layer()
                    async_to_sync(channel_layer.group_send)(
                        f'env_system_{system.unique_identifier}',
                        {
                            'type': 'status_update',
                            'system_id': str(system.unique_identifier),
                            'is_active': system.is_active,
                            'status': 'unreachable'
                        }
                    )
            except Exception as e:
                logger.exception(f"[TIMEOUT ERROR] Failed to mark system {env_system.pk}: {e}")

        timer = Timer(5.0, timeout_check)
        timer.start()
        pending_confirmations[env_system.unique_identifier] = timer

    except Exception as e:
        logger.error(f"Failed to publish MQTT message for {env_system.unique_identifier}: {e}")
    




def handle_check_request(unique_id, client):
    """
    Handles check requests to verify if a sensor is registered in the system.

    Parameters:
        unique_id (str): The unique identifier of the sensor.
        client (mqtt.Client): The MQTT client instance to publish the response.
    """
    registered = SensorUnit.objects.filter(unique_identifier=unique_id).exists()

    if registered == False:
        registered = EnvironmentalSystem.objects.filter(unique_identifier=unique_id).exists()
    response = {"registered": registered}
    client.publish(f'sensor/check/response/{unique_id}', json.dumps(response))
    logger.info(f"Check response for {unique_id}: {'registered' if registered else 'not registered'}")

def handle_registration(unique_id):
    """
    Handles the registration of a new sensor or acknowledges an existing registration request.

    Parameters:
        unique_id (str): The unique identifier of the sensor.
    """
    obj, created = PendingSensorRegistration.objects.get_or_create(unique_identifier=unique_id)
    if created:
        logger.info(f"Pending registration created for sensor: {unique_id}")
    else:
        logger.info(f"Sensor {unique_id} registration already requested.")


def handle_sensor_data(unique_id, data):
    """
    Handles incoming sensor data by updating or creating sensor records in the database.

    Parameters:
        unique_id (str): The unique identifier of the sensor.
        data (dict): The sensor data to be recorded.
    """
    try:
        logger.info(f"Received data for {unique_id}: {data}")

        if not data or not isinstance(data, dict):
            logger.error(f"Invalid data payload for sensor {unique_id}: {data}")
            return

        sensor = SensorUnit.objects.filter(unique_identifier=unique_id).first()

        if sensor:
            logger.debug(f"Found sensor with unique_identifier {unique_id}.")
            sanitized_data = {sanitize_string(k): sanitize_string(v) for k, v in data.items()}

            sensor.update_sensor_data(data)
            sensor.handle_thresholds(data)


            if sensor.greenhouse.automated:
                greenhouse_control = Greenhouse.GreenhouseControl(sensor.greenhouse)
                greenhouse_control.adjust_environmental_systems()

        else:
            logger.warning(f"No matching sensor found for unique_identifier {unique_id}.")
            
        with open('data/sensor_data.csv',mode='a', newline='', encoding='utf-8')as file:
            writer = csv.writer(file)
            if file.tell() == 0:
                writer.writerow(['timestamp', 'unique_id', 'sensor_data'])

            timestamp = now().isoformat()
            writer.writerow([timestamp, unique_id, json.dumps(sanitized_data)])

        
    except Exception as e:
        logger.error(f"Failed to update sensor data for {unique_id}: {e}")

def publish_sensor_settings(sensor):
    """
    Publishes the updated settings for a sensor to the MQTT broker as a retained message.

    Parameters:
        sensor (SensorUnit): The sensor instance whose settings need to be published.
    """
    try:
        settings = {"data_frequency": sensor.data_frequency}
        topic = f'sensor/settings/response/{sensor.unique_identifier}'

        publish.single(
            topic,
            payload=json.dumps(settings),
            qos=1,
            hostname=MQTT_HOST,
            port=MQTT_PORT,
            tls={'ca_certs': ca_path, 'tls_version': ssl.PROTOCOL_TLSv1_2},
            auth={'username': 'smart_greenhouse', 'password': 'radegast1'},
            retain=True
        )
        logger.info(f"Published settings for {sensor.unique_identifier}: {settings}")
    except Exception as e:
        logger.error(f"Failed to publish settings for {sensor.unique_identifier}: {e}")


def handle_settings_request(unique_id, client):
    """
    Handles requests for sensor settings and publishes them to the appropriate MQTT topic.

    Parameters:
        unique_id (str): The unique identifier of the sensor.
        client (mqtt.Client): The MQTT client instance to publish the settings.
    """
    try:
        sensor = SensorUnit.objects.get(unique_identifier=unique_id)
        settings = {"data_frequency": sensor.data_frequency}
        client.publish(f'sensor/settings/response/{unique_id}', json.dumps(settings), retain = True)
        logger.info(f"Settings sent to {unique_id}.")

    except SensorUnit.DoesNotExist:
        logger.warning(f"Settings request for unregistered sensor {unique_id}.")


if not os.path.exists(ca_path):
    logger.error(f"CA Certificate file not found at {ca_path}")
    exit(1)


client.on_connect = on_connect
client.on_message = on_message



if __name__ == "__main__":

    try:
        client.connect(MQTT_HOST, MQTT_PORT, 60)
        client.loop_start()

        signal.signal(signal.SIGINT, graceful_shutdown)
        signal.signal(signal.SIGTERM, graceful_shutdown)
        logger.info("MQTT communication module running. Press Ctrl+C to exit.")
        while True:
            time.sleep(1)
    except Exception as e:
        logger.exception(f"Connection failed: {e}")
        client.loop_stop()
