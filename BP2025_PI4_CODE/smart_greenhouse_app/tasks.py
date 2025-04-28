"""
Celery task definitions for the Django project.

This module contains asynchronous tasks that handle periodic background processes such as sensor status checks,
weather data fetching and analysis, and environmental system adjustments based on automation settings.
These tasks are scheduled to run at specific intervals or can be triggered as needed.

Dependencies:
- Celery: for task queue management.
- Django: for ORM and email functionalities.
"""
from celery import shared_task
from django.core.mail import send_mail
from .models import SensorUnit, WeatherForecast, Greenhouse
import requests
from .utils import fetch_location_via_ip  # Assuming fetch_gps_coordinates is moved to utils.py
from django.utils import timezone


import logging

logger = logging.getLogger(__name__)

@shared_task
def check_sensor_statuses():
    """
    Periodically checks the status of all registered sensors and sends an email alert if any sensor is offline.
    """
    sensors = SensorUnit.objects.all()
    for sensor in sensors:
        if not sensor.is_online():
            send_mail(
                'Sensor Offline',
                f'The sensor {sensor.identifier} is offline.',
                'from@example.com',
                ['to@example.com'],
                fail_silently=False,
            )


@shared_task
def fetch_and_analyze_weather_task():
    """
    Fetches weather forecast data using latitude and longitude obtained from the utility function and analyzes the
    temperature to detect cold waves. Updates or creates weather forecast records accordingly.
    """
    print("Fetching location coordinates...")
    lat, lon = fetch_location_via_ip()

    if lat is None or lon is None:
        print("Failed to fetch location coordinates.")
        return "Failed to fetch location coordinates."

    url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&daily=temperature_2m_min&timezone=auto"
    
    try:
        response = requests.get(url)
        data = response.json()

        daily_forecasts = data.get('daily', {})
        temperature_mins = daily_forecasts.get('temperature_2m_min', [])
        forecast_dates = daily_forecasts.get('time', [])

        cold_wave_threshold = 5

        for i, temp in enumerate(temperature_mins):
            date = forecast_dates[i]
            cold_wave_detected = temp < cold_wave_threshold
            message = 'Cold wave likely.' if cold_wave_detected else 'Conditions normal.'

            WeatherForecast.objects.update_or_create(
                forecast_date=date,
                defaults={
                    'message': message,
                    'minimum_temperature': temp,
                    'forecast_retrieved': timezone.now()
                }
            )

        print("Forecasts updated successfully.")
        return "Forecasts updated."
    except Exception as e:
        print(f"An error occurred: {str(e)}")
        return f"An error occurred: {str(e)}"

@shared_task
def adjust_systems_task():
    """
    Adjusts the environmental systems of all automated greenhouses based on their sensor readings and predefined
    settings. Logs the activity and outcomes of the adjustments.
    """
    logger.info("Starting task to adjust systems based on automation settings")
    greenhouses = Greenhouse.objects.filter(automated=True)
    if not greenhouses.exists():
        logger.info("No automated greenhouses found.")
        return "No automated greenhouses found."
    
    for greenhouse in greenhouses:
        logger.info(f"Checking systems for automated greenhouse: {greenhouse.name}")
        controller = Greenhouse.GreenhouseControl(greenhouse)
        controller.adjust_environmental_systems()
    return "Adjustment process completed."

