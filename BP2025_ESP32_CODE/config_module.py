"""
Configuration management for the smart greenhouse system.

This module provides functions for loading, editing, and reloading configuration settings
from a JSON file used across the microcontroller.
"""

import json
import os
from utils_module import log

cfg = {}

def reload_config():
    """
    Reloads the configuration file if it has been modified.

    This function checks the last modification time of 'config.json' and reloads the configuration
    if a change is detected.
    """
    global last_mod_time
    current_mod_time = os.stat('config.json')[8]
    if current_mod_time != last_mod_time:
        log("Configuration file changed. Reloading...")
        load_config('config.json')
        last_mod_time = current_mod_time

def load_config(file_path):
    """
    Loads a JSON configuration file.

    Parameters:
        file_path (str): Path to the JSON configuration file.

    Returns:
        dict: The loaded configuration as a dictionary.

    Raises:
        Exception: If the file cannot be loaded.
    """
    global cfg
    try:
        with open(file_path, 'r') as f:
            cfg = json.load(f)
        return cfg
    except Exception as e:
        raise Exception(f"Error loading config file: {e}")

def edit_config(file_path, new_data):
    """
    Edits a JSON configuration file by updating specific keys without overwriting the entire file.

    Parameters:
        file_path (str): Path to the JSON configuration file.
        new_data (dict): Dictionary containing new data to update in the configuration.

    Raises:
        Exception: If the file cannot be edited or saved.
    """
    try:
        config_data = {}
        with open(file_path, 'r') as f:
            config_data = json.load(f)
        
        for key, value in new_data.items():
            if key in config_data and isinstance(config_data[key], dict) and isinstance(value, dict):
                config_data[key].update(value)
            else:
                config_data[key] = value
        
        with open(file_path, 'w') as f:
            json.dump(config_data, f)
            load_config(file_path)
            
        reload_config()
    except Exception as e:
        raise Exception(f"Error editing config file: {e}")

# Load configuration at startup
load_config('config.json')
last_mod_time = os.stat('config.json')[8]