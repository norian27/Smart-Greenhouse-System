"""
WebSocket consumers for real-time updates in the smart greenhouse system.

This module defines asynchronous WebSocket consumers that handle real-time sensor data updates
and environmental system status changes.
"""

import json
import logging
from channels.generic.websocket import AsyncWebsocketConsumer


logger = logging.getLogger(__name__)

class SensorDataConsumer(AsyncWebsocketConsumer):
    """
    Consumer for broadcasting real-time sensor data updates to connected WebSocket clients.

    Attributes:
        group_name (str): The WebSocket group name for broadcasting sensor updates.
    """
    async def connect(self):
        """
        Handles the WebSocket connection establishment.

        Adds the WebSocket connection to the sensor updates group and accepts the connection.
        """

        self.group_name = "sensor_updates"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        print(f"WebSocket connected: {self.channel_name}")

    async def disconnect(self, close_code):
        """
        Handles the WebSocket disconnection.

        Removes the WebSocket connection from the sensor updates group.

        Parameters:
            close_code (int): WebSocket close code.
        """        
        await self.channel_layer.group_discard(self.group_name, self.channel_name)
        print(f"WebSocket disconnected: {self.channel_name}")

    async def receive(self, text_data):
        """
        Receives data from WebSocket clients.

        Not used in this consumer as the server only sends data.

        Parameters:
            text_data (str): Text data received from the WebSocket client.
        """
        pass

    async def sensor_data_update(self, event):
        """
        Sends a sensor data update to the WebSocket client.

        Parameters:
            event (dict): Event data containing the sensor ID.
        """
        await self.send(text_data=json.dumps({
            'type': 'sensor_update',
            'sensor_id': event['sensor_id']
        }))


class EnvSystemConsumer(AsyncWebsocketConsumer):
    """
    Consumer for broadcasting real-time environmental system status updates.

    Attributes:
        system_id (str): The ID of the environmental system.
        room_group_name (str): The WebSocket group name for broadcasting status updates.
    """
    async def connect(self):
        """
        Handles the WebSocket connection establishment for an environmental system.

        Adds the WebSocket connection to the specific system's status update group.
        """
        self.system_id = self.scope["url_route"]["kwargs"]["system_id"]
        self.room_group_name = f"env_system_{self.system_id}"

        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        """
        Handles the WebSocket disconnection for an environmental system.

        Removes the WebSocket connection from the specific system's status group.

        Parameters:
            close_code (int): WebSocket close code.
        """
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)
        
    async def status_update(self, event):
        """
        Sends a status update for an environmental system to the WebSocket client.

        Parameters:
            event (dict): Event data containing system ID, active state, and status string.
        """
        logger.debug(f"Updating status for {event['system_id']} to {event['is_active']}")

        await self.send(text_data=json.dumps({
            'type': 'status_update',
            'system_id': event['system_id'],
            'is_active': event['is_active'],
            'status': event['status']
        }))