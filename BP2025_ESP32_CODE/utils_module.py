"""
Utility functions for logging and unique identifier generation.

This module provides helper functions used across the smart greenhouse project,
including message logging with timestamps and getting device unique identifier.
"""
from config_module import *
import time
import network
def log(message):
    """
    Logs a message with a timestamp.

    Parameters:
        message (str): The message to log.
    """
    print(f"[LOG] {time.time()}: {message}")

def get_unique_identifier():
    """
    Retrieves the device's MAC address and formats it as a unique identifier.

    Returns:
        str: The unique identifier string based on the device's MAC address.
    """
    mac = network.WLAN(network.STA_IF).config('mac')
    return ''.join(['{:02x}'.format(b) for b in mac])
