"""
Network utilities for connecting to Wi-Fi.

This module provides functions to establish a Wi-Fi connection
using credentials defined in the configuration file.
"""

from config_module import *
from utils_module import log
import time
import network


def connect_to_wifi(retries=3, delay=5):
    """
    Connects the device to Wi-Fi using configured network credentials.

    Parameters:
        retries (int): Number of retry attempts.
        delay (int): Delay between retries in seconds.

    Raises:
        OSError: If unable to connect after all retries.
    """
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    for _ in range(retries):
        if not wlan.isconnected():
            log('Connecting to network...')
            wlan.connect(cfg['network']['ssid'], cfg['network']['password'])
            for _ in range(delay * 10):
                if wlan.isconnected():
                    break
                time.sleep(0.1)
        if wlan.isconnected():
            log(f'Network config: {wlan.ifconfig()}')
            return 
        else:
            log(f'Failed to connect to network. Retrying...')
    raise OSError("Failed to connect to WiFi after multiple retries.")
