"""
Django models for managing greenhouse data and control systems.

This module defines Django models for representing various aspects of a greenhouse, including sensors,
environmental systems, alerts, and weather forecasts. These models are used to store data related to
the greenhouse environment and to control its systems automatically.
"""
from django.db import models
from django.utils.timezone import now
from django.utils import timezone
from django.test import RequestFactory
from datetime import timedelta
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
import paho.mqtt.publish as publish
import ssl
import datetime
import json
import logging

logger = logging.getLogger("smart_greenhouse")


def sanitize_string(value):
    """
    Replaces unsupported Unicode characters in a string.

    Args:
        value (str): The string or object to sanitize.

    Returns:
        str: The sanitized string if input is a string, otherwise the original value.
    """

    if isinstance(value, str):
        return value.replace('\u2014', '-')
    return value


class Greenhouse(models.Model):
    """
    Represents a greenhouse unit.

    Attributes:
        name (str): The name of the greenhouse.
        location (str): The location of the greenhouse.
        contents (str, optional): The contents of the greenhouse.
        automated (bool): Indicates whether the greenhouse is automated.
    """
    name = models.CharField(max_length=100)
    location = models.CharField(max_length=255)
    contents = models.CharField(max_length=255, blank=True, null=True)
    automated = models.BooleanField(default=False)

    def toggle_environmental_system_automatically(self, env_system, action):
        """
        Toggles the environmental system automatically based on the action.

        Args:
            env_system (EnvironmentalSystem): The environmental system to toggle.
            action (str): The action to perform ('activate' or 'deactivate').
        """

        # MQTT Broker Configuration
        MQTT_HOST = '10.42.0.1'
        MQTT_PORT = 8883
        MQTT_CA_CERTS = '/etc/mosquitto/certs/ca.crt'
        MQTT_USERNAME = 'smart_greenhouse'
        MQTT_PASSWORD = 'radegast1'

        if action == 'activate':
            can_activate = env_system.activate()
        elif action == 'deactivate':
            can_activate = env_system.deactivate()

        if can_activate:
            env_system.refresh_from_db()

            message = {
                'unique_identifier': env_system.unique_identifier,
                'action': action
            }
            if env_system.env_type == 'Window':
                if hasattr(env_system, 'current_angle'):
                    message['angle'] = env_system.current_angle
                else:
                    logger.warning("Window system %s has no current_angle field!", env_system.name)	

            try:
                publish.single(
                    'system/control/command',
                    json.dumps(message),
                    hostname=MQTT_HOST,
                    port=MQTT_PORT,
                    tls={'ca_certs': MQTT_CA_CERTS, 'tls_version': ssl.PROTOCOL_TLSv1_2},
                    auth={'username': MQTT_USERNAME, 'password': MQTT_PASSWORD},
                    retain=False
                )
                logger.info("Published control message for %s to %s", env_system.name, action)	
            except Exception as e:
                logger.error("Failed to publish MQTT message for %s: %s", env_system.name, e)
        else:
            logger.info("Action %s not performed for %s due to cooldown constraints.", action, env_system.name)
        env_system.refresh_from_db()
    

    class GreenhouseControl:
        """
        Used for autonomic control of the greenhouse's environmental systems.s

        Attributes:
            CONTROL_MAP (dict): A dictionary mapping control codes to their descriptions.
        """
        CONTROL_MAP = {
            'HU': ('humidity', 'Humidity'),
            'TE': ('temperature', 'Cooling', 'Heating', 'Window'),
            'SM': ('soil_moisture', 'Sprinkler'),
        }
        

        def __init__(self, greenhouse):
            """
            Initializes the GreenhouseControl instance.

            Args:
                greenhouse (Greenhouse): The greenhouse instance to control.
            """
            self.greenhouse = greenhouse

        def adjust_environmental_systems(self):
            """Adjusts the environmental systems of the greenhouse based on active alerts."""
            if not self.greenhouse.automated:
                logger.info("Greenhouse %s is not automated; skipping control.", self.greenhouse.name)	
                return

            logger.info("Adjusting systems for greenhouse %s", self.greenhouse.name)	

            active_alerts = Alert.objects.filter(sensor__greenhouse=self.greenhouse, is_active=True)

            for alert in active_alerts:
                sensor = alert.sensor
                logger.info("Processing alert for sensor %s: %s", sensor.identifier, alert.message)	
                sensor_data = sensor.get_last_data()

                if not sensor_data:
                    continue

                applicable_controls, used_keys = self.get_control_details(sensor.sensor_type)


                for env_system in self.greenhouse.env_systems.all():
                    if env_system.env_type not in applicable_controls:
                        continue
                    
                    for data_key in used_keys:
                        self.evaluate_and_act(env_system, sensor, sensor_data, data_key)

        def get_control_details(self, sensor_type_json):
            """
            Retrieves applicable environmental controls and data keys for a given sensor type.

            Args:
                sensor_type_json (str): JSON string describing the sensor's data types.

            Returns:
                tuple: A tuple containing a list of applicable control types and a list of used sensor data keys.
            """

            try:
                if not sensor_type_json or not sensor_type_json.strip():
                    logger.error("sensor_type_json is empty or blank.")	
                    return [], []

                sensor_keys = json.loads(sensor_type_json) if sensor_type_json else []
                applicable_controls = set()
                used_keys = []

                for key in sensor_keys:
                    for code, controls in self.CONTROL_MAP.items():
                        if key.lower() in [c.lower().replace(" ", "_") for c in controls]:
                            applicable_controls.update(controls[1:])
                            used_keys.append(controls[0])

                logger.debug("Applicable controls: %r; used keys: %r", applicable_controls, used_keys)	
                return list(applicable_controls), used_keys
            except json.JSONDecodeError as e:
                logger.error("Failed to decode sensor_type_json %r: %s", sensor_type_json, e)
            return [], []

        def evaluate_and_act(self, env_system, sensor, sensor_data, data_key):
            """
            Evaluates environmental system state and triggers actions if needed based on sensor data.

            Args:
                env_system (EnvironmentalSystem): The environmental system to evaluate (e.g., Cooling, Sprinkler).
                sensor (SensorUnit): The sensor providing the data.
                sensor_data (dict): The latest sensor readings.
                data_key (str): The key from the sensor data to evaluate.

            Returns:
                None
            """
 
            if env_system.env_type == 'Sprinkler':
                soil = sensor_data.get('soil_moisture')
                humidity = sensor_data.get('humidity')

                if soil is None or humidity is None:
                    logger.warning("Missing data for sprinkler evaluation (soil=%s, humidity=%s)", soil, humidity)	
                    return

                target = env_system.target_value
                tolerance = 0.5

                should_activate = soil <= (target + tolerance) or humidity <= (target + tolerance)
                should_deactivate = soil > (target + tolerance) and humidity > (target + tolerance)

                logger.debug("Sprinkler evaluation — soil=%s, humidity=%s, target=%s", soil, humidity, target)	
                if should_activate and not env_system.is_active:
                    logger.info("Sprinkler %s needs activation", env_system.name)	
                    self.toggle_environmental_system(env_system, 'activate')
                elif should_deactivate and env_system.is_active:
                    logger.info("Sprinkler %s needs deactivation", env_system.name)	
                    self.toggle_environmental_system(env_system, 'deactivate')

            elif env_system.env_type == 'Window':
                temperature = sensor_data.get('temperature')
                if temperature is None:
                    logger.warning("No temperature data for window control evaluation for %s", env_system.name)	
                    return
            
                threshold = sensor.thresholds.filter(key='temperature').first()
                if threshold:
                    target = threshold.threshold_high
                else:
                    target = env_system.target_value
                    logger.warning("No temperature threshold found; falling back to target_value=%s", target)	

                hysteresis = 1.0

                should_open = temperature >= (target + hysteresis)
                should_close = temperature <= (target - hysteresis)

                logger.debug("Window control eval — temp=%s, target=%s, hysteresis=±%s", temperature, target, hysteresis)	
                if should_open:
                    logger.info("Window %s needs to be opened", env_system.name)	
                    if hasattr(env_system, 'windowcontrolsystem'):
                        window_control = env_system.windowcontrolsystem
                        if window_control.current_angle != 90.0:
                            window_control.current_angle = 90.0
                            window_control.save(update_fields=['current_angle'])
                            if not env_system.is_active:
                                self.toggle_environmental_system(env_system, 'activate')

                elif should_close:
                    logger.info("Window %s needs to be closed", env_system.name)	
                    if hasattr(env_system, 'windowcontrolsystem'):
                        window_control = env_system.windowcontrolsystem
                        if window_control.current_angle != 0.0:
                            window_control.current_angle = 0.0
                            window_control.save(update_fields=['current_angle'])
                            if not env_system.is_active:
                                self.toggle_environmental_system(env_system, 'activate')
            
            
            else:
                env_type_to_data_key = {
                    'Cooling': 'temperature',
                    'Heating': 'temperature',
                    'Humidity': 'humidity',
                }

                data_key = env_type_to_data_key.get(env_system.env_type)
                if not data_key:
                    logger.error("No data mapping found for env_type=%s", env_system.env_type)	
                    return

                current_value = sensor_data.get(data_key)
                if current_value is None:
                    return

                target_value = env_system.target_value
                logger.debug("%s for sensor %s: current=%s, target=%s", env_system.env_type, sensor.identifier, current_value, target_value)	

                action_needed = self.determine_action(env_system, current_value, target_value)
                if action_needed:
                    logger.info("Action needed for %s: %s", env_system.name, action_needed)	
                    self.toggle_environmental_system(env_system, action_needed)

        def determine_action(self, env_system, current_value, target_value):
            """
            Determines the action needed based on the current and target values.

            Args:
                env_system (EnvironmentalSystem): The environmental system.
                current_value (float): The current value.
                target_value (float): The target value.

            Returns:
                str: The action needed ('activate', 'deactivate', or None).
            """
            tolerance = 0.5
            hysteresis = 1.0


            if env_system.env_type == 'Cooling' and current_value >= (target_value + hysteresis):
                return 'deactivate'
            elif env_system.env_type == 'Cooling' and current_value <= (target_value - hysteresis):
                return 'activate'
            elif env_system.env_type == 'Heating' and current_value <= (target_value - hysteresis):
                return 'activate'
            elif env_system.env_type == 'Heating' and current_value >= (target_value + hysteresis):
                return 'deactivate'
            return None

        def toggle_environmental_system(self, env_system, action):
            """
            Toggles the environmental system.

            Args:
                env_system (EnvironmentalSystem): The environmental system.
                action (str): The action to perform ('activate' or 'deactivate').
            """
            from mqtt_communication import publish_control_command


            if action == 'activate':
                env_system.activate()
            else:
                env_system.deactivate()

            env_system.save()
            publish_control_command(env_system, action)


    def __str__(self):
        """
        Returns the string representation of the greenhouse.

        Returns:
            str: The string representation.
        """
        return self.name
    
    def sensor_count(self):
        """
        Returns the number of sensors associated with the greenhouse.

        Returns:
            int: The number of sensors.
        """
        return self.sensors.count()


class SensorUnit(models.Model):
    """
    Represents a sensor unit in the greenhouse.

    Attributes:
        greenhouse (ForeignKey): The greenhouse to which the sensor belongs.
        unique_identifier (str): The unique identifier of the sensor.
        identifier (str): The identifier of the sensor.
        last_check_in (DateTimeField): The timestamp of the last check-in.
        last_data (TextField): The last data received from the sensor.
        data_frequency (IntegerField): Frequency in seconds for data transmission.
        settings_updated (BooleanField): Flag to indicate if settings are updated and pending to be picked up by the sensor.
        sensor_type (str): The type of sensor.
    """    
    greenhouse = models.ForeignKey('Greenhouse', on_delete=models.CASCADE, related_name='sensors')
    unique_identifier = models.CharField(max_length=255, unique=True, db_index=True)
    identifier = models.CharField(max_length=100)
    last_check_in = models.DateTimeField(null=True, blank=True)
    last_data = models.TextField(blank=True, null=True)
    data_frequency = models.IntegerField(default=300, help_text="Frequency in seconds for data transmission.")
    settings_updated = models.BooleanField(default=False, help_text="Flag to indicate if settings are updated and pending to be picked up by the sensor.")
    sensor_type = models.CharField(max_length=255, blank=True, help_text="Dynamic sensor type based on data keys.")

    def update_sensor_data(self, data):
        """
        Updates the sensor data.
        """

        
        if not data:
            logger.error("Received empty data for sensor %s", self.identifier)	
            return
    
        try:
            sanitized_data = {sanitize_string(k): sanitize_string(v) for k, v in data.items()}
            self.last_data = json.dumps(sanitized_data)
            self.last_check_in = now()
            normalized_keys = sorted([key.lower() for key in sanitized_data.keys()])

            if normalized_keys:
                self.sensor_type = json.dumps(normalized_keys)
            else:
                logger.warning("No keys found in data for sensor %s", self.identifier)	
                self.sensor_type = "[]"

            self.save(update_fields=['last_data', 'last_check_in', 'sensor_type'])
            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.group_send)(
                "sensor_updates",
                {
                    "type": "sensor_data_update",
                    "sensor_id": self.unique_identifier
                }
            )
        except (TypeError, ValueError) as e:
            logger.warning("Failed to update sensor data for %s: %s", self.unique_identifier, e)
    

    def handle_thresholds(self, data):
        """
        Handles sensor thresholds.

        Args:
            data (dict): The sensor data.
        """
        for key,value in data.items():
            threshold = self.thresholds.filter(key=key).first()
            if threshold:
                self.check_and_handle_alert(key, value, threshold.threshold_low, threshold.threshold_high)



    def check_and_handle_alert(self, data_type, value, alert_low, alert_high):
        """
        Checks and handles alerts based on sensor thresholds.

        Args:
            data_type (str): The type of data.
            value (float): The value of the data.
            alert_low (float): The low threshold for the alert.
            alert_high (float): The high threshold for the alert.
        """
        if value is None:
            return
        
        logger.debug("%s: %s (low=%s; high=%s)", data_type, value, alert_low, alert_high)	
    
        alert_message = None

        existing_alert = Alert.objects.filter(
            sensor=self,
            message__startswith=data_type.capitalize(),
            is_active=True
        ).first()
    
        if existing_alert:
            if alert_low < value < alert_high:
                existing_alert.is_active = False
                existing_alert.resolved_timestamp = now()
                existing_alert.save()
        else:
            if value <= alert_low:
                alert_message = f"{sanitize_string(data_type).capitalize()} below threshold: {value}"
            elif value >= alert_high:
                alert_message = f"{sanitize_string(data_type).capitalize()} above threshold: {value}"

            if alert_message:
                Alert.objects.create(sensor=self, message=alert_message, value=value)

    def get_last_data(self):
        """
        Retrieves the last sensor data.

        Returns:
            dict: The last sensor data.
        """

        logger.debug("Raw last_data for sensor %s: %r", self.identifier, self.last_data)	
        try:
            if not self.last_data or self.last_data.strip() == "":
                return{}
            data = json.loads(self.last_data)
            logger.debug("Parsed data for sensor %s: %r", self.identifier, data)	
            return data
        except json.JSONDecodeError as e:
            logger.error("Failed to decode JSON for sensor %s: %s", self.identifier, e)	
            return {}
        except TypeError as e:
            logger.error("Invalid data type for sensor %s: %s", self.identifier, e)	
            return {}
    

    def is_online(self):
        """
        Checks if the sensor is online.

        Returns:
            bool: True if the sensor is online, False otherwise.
        """
        if self.last_check_in and self.data_frequency:
            grace_period = 10
            expected_online_window = self.data_frequency + grace_period
            return now() - self.last_check_in <= timedelta(seconds=expected_online_window)
        return False

    def update_settings(self, data_frequency=None):
        """
        Updates sensor settings and ensures the changes are reflected in the database.
    
        Args:
            data_frequency (int, optional): The new data frequency to set.
            other_settings (dict, optional): Additional settings to update.
        """

        if data_frequency is not None:
            self.data_frequency = data_frequency
            self.settings_updated = True
            logger.debug("Settings updated flag for %s: %s", self.identifier, self.settings_updated)	
            self.save(update_fields=['data_frequency','settings_updated'])

        try:
            from mqtt_communication import publish_sensor_settings
            publish_sensor_settings(self)
            self.settings_updated = False
            self.save(update_fields=['settings_updated'])
        except Exception as e:
            logger.error("Failed to publish settings for %s: %s", self.identifier, e)	
        


    def save(self, *args, **kwargs):
        """
        Saves the sensor instance.

        Args:
            *args: Variable length argument list.
            **kwargs: Arbitrary keyword arguments.
        """

        logger.debug("Saving sensor %s with last_data: %r", self.identifier, self.last_data)	
        if self.last_data is None:
            self.last_data = json.dumps({})
        elif not isinstance(self.last_data, str):
            self.last_data = json.dumps({sanitize_string(k): sanitize_string(v) for k, v in self.last_data.items()})

        super().save(*args, **kwargs)
        self.manage_thresholds()


    
    def manage_thresholds(self):
        """
        Manages sensor thresholds.
        """
        if not self.sensor_type:
            return
    
        try:
            keys = json.loads(self.sensor_type)
        except json.JSONDecodeError:
            logger.error("Could not parse sensor_type JSON: %s", self.sensor_type)
            return
        existing_thresholds = set(self.thresholds.values_list('key', flat=True))
    
        for key in keys:
            if key not in existing_thresholds:
                SensorThreshold.objects.create(sensor=self, key=key)
    
        for key in existing_thresholds - set(keys):
            self.thresholds.filter(key=key).delete()

    def __str__(self):
        """
        Returns the string representation of the sensor.

        Returns:
            str: The string representation.
        """
        return self.identifier


class SensorThreshold(models.Model):
    """
    Represents thresholds for a sensor unit.

    Attributes:
        sensor (ForeignKey): The sensor associated with the thresholds.
        key (CharField): The data key (e.g., temperature, humidity).
        threshold_low (FloatField): The lower threshold for this key.
        threshold_high (FloatField): The upper threshold for this key.
    """
    sensor = models.ForeignKey(SensorUnit, on_delete=models.CASCADE, related_name='thresholds')
    key = models.CharField(max_length=50, help_text="Data key (e.g., temperature, humidity).")
    threshold_low = models.FloatField(default=0.0, help_text="Lower threshold.")
    threshold_high = models.FloatField(default=100.0, help_text="Upper threshold.")

    class Meta:
        unique_together = ('sensor', 'key')

    def __str__(self):
        return f"Threshold for {self.sensor.identifier} - {self.key}: {self.threshold_low} to {self.threshold_high}"

    
class PendingSensorRegistration(models.Model):
    """
    Represents a pending sensor registration request.

    Attributes:
        unique_identifier (CharField): The unique identifier of the sensor.
        registration_request_time (DateTimeField): The time when the registration request was made.
        status (CharField): The status of the registration request ('pending' or 'confirmed').
    """
    unique_identifier = models.CharField(max_length=255, unique=True)
    registration_request_time = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=10, choices=[('pending', 'Pending'), ('confirmed', 'Confirmed')], default='pending')

    def __str__(self):
        return self.unique_identifier
    
class Alert(models.Model):
    """
    Represents an alert triggered by a sensor.

    Attributes:
        sensor (ForeignKey): The sensor unit associated with the alert.
        timestamp (DateTimeField): The time when the alert was triggered.
        message (TextField): The message associated with the alert.
        value (FloatField): The value associated with the alert.
        is_active (BooleanField): Indicates if the alert is currently active.
        resolved_timestamp (DateTimeField): The time when the alert was resolved (if resolved).
    """
    sensor = models.ForeignKey(SensorUnit, on_delete=models.CASCADE, related_name='alerts')
    timestamp = models.DateTimeField(auto_now_add=True)
    message = models.TextField()
    value = models.FloatField()
    is_active = models.BooleanField(default=True, help_text="Indicates if the alert is currently active.")
    resolved_timestamp = models.DateTimeField(null=True, blank=True, help_text="The time when the alert was resolved.")

    def __str__(self):
        return f"Alert for {self.sensor.identifier} at {self.timestamp.strftime('%Y-%m-%d %H:%M:%S')}"
    
 
class WeatherForecast(models.Model):
    """
    Represents a weather forecast.

    Attributes:
        forecast_date (DateField): The date of the forecast.
        message (TextField): The forecast message.
        minimum_temperature (FloatField): The minimum temperature forecasted.
        forecast_retrieved (DateTimeField): The time when the forecast was retrieved.
    """
    forecast_date = models.DateField()
    message = models.TextField()
    minimum_temperature = models.FloatField()
    forecast_retrieved = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Weather Forecast for {self.forecast_date}: {self.message}"
    
    
class EnvironmentalSystem(models.Model):
    """
    Represents an environmental system in a greenhouse.

    Attributes:
        name (CharField): The name of the environmental system.
        unique_identifier (CharField): The unique identifier of the environmental system.
        is_active (BooleanField): Indicates if the environmental system is currently active.
        env_type (CharField): The type of environmental system ('Cooling', 'Heating', 'Sprinkler').
        greenhouse (ForeignKey): The greenhouse associated with the environmental system.
        target_value (FloatField): The target value for the environmental system.
        last_activated (DateTimeField): The time when the environmental system was last activated.
        cool_down (IntegerField): The cooldown period for the environmental system.
    """
    class SystemType(models.TextChoices):
        COOLING = 'Cooling', ('Cooling')
        HEATING = 'Heating', ('Heating')
        SPRINKLER = 'Sprinkler', ('Sprinkler')
        WINDOW_CONTROL = 'Window', ('Window')

    name = models.CharField(max_length=100)
    unique_identifier = models.CharField(max_length=255, unique=True, db_index=True)
    is_active = models.BooleanField(default=False)
    status = models.CharField(max_length = 20, choices=[('idle', 'Idle'), ('waiting', 'Waiting'), ('unreachable', 'Unreachable')], default = 'idle')
    env_type = models.CharField(
        max_length=10,
        choices=SystemType.choices,
        default=SystemType.COOLING
    )
    identifier = models.CharField(max_length=100)
    greenhouse = models.ForeignKey('Greenhouse', on_delete=models.CASCADE, related_name='env_systems')
    target_value = models.FloatField(default=0.0)
    last_activated = models.DateTimeField(null=True, blank=True)
    data = models.TextField(blank=True, null= True)

    def activate(self):
        """
        Activates the environmental system if it's not already active.

        Returns:
            bool: True if the action was performed, False otherwise.
        """
        current_time = timezone.now()
        self.is_active = True
        self.last_activated = current_time
        self.save()
        logger.debug("Activated %s",self.name)
        
        return True



    def deactivate(self):
        """
        Deactivates the environmental system.

        Returns:
            bool: True if the action was performed, False otherwise.
        """
        if  self.is_active:
            self.is_active = False
            self.save()
            logger.debug("Deactivated %s",self.name)
            return True  # Action was performed


    def __str__(self):
        """
        Returns a string representation of the environmental system.

        Returns:
            str: String representation of the environmental system.
        """
        return f"{self.name} ({self.get_env_type_display()})"


class WindowControlSystem(EnvironmentalSystem):
    current_angle = models.FloatField(default=0.0, help_text="Current angle of the window system.")

    def adjust_angle(self, new_angle):
        """
        Adjusts the window system to a specified angle.

        Args:
            new_angle (float): The desired window angle in degrees.
        """

        self.current_angle = new_angle
        self.save()

    def activate(self):
        """
        Opens the window to 90 degrees, if Greenhouse is automaded, and it activates the window control system.
    
        Returns:
            bool: True if the activation was successful, False otherwise.
        """

        if self.greenhouse.automated:
            self.adjust_angle(90.0)
        super().activate()  # Call the parent class's activate method
        
    def deactivate(self):
        """
        Closes the window to 0 degrees, if Greenhouse is automated, and deactivates the window control system.
    
        Returns:
            bool: True if the deactivation was successful, False otherwise.
        """

        # Logic to close the window (adjust the angle to 0 degrees or fully closed)
        if self.greenhouse.automated:
            self.adjust_angle(0.0)
        super().deactivate()