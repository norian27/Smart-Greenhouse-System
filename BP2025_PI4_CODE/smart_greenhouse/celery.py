"""
Celery configuration for the Django project.

This module sets up the Celery application for asynchronous task queueing based on the Django settings. It includes
scheduling of periodic tasks using Celery beat. The tasks are designed to run functions at specific intervals to fetch weather data, that could be later used for dynamic threshold adjustments.
"""
from __future__ import absolute_import, unicode_literals
import os
from celery import Celery
from celery.schedules import crontab

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'smart_greenhouse.settings')

# Create a new Celery instance and configure it using the settings from Django.
app = Celery('smart_greenhouse')

app.config_from_object('django.conf:settings', namespace='CELERY')

app.autodiscover_tasks()

app.conf.timezone = 'CET'

app.conf.beat_schedule = {
        'fetch_and_analyze_weather_every_6_hours': {
        'task': 'smart_greenhouse_app.tasks.fetch_and_analyze_weather_task',
        'schedule': crontab(minute=0, hour='*/6'),  # Runs at every 6th hour
    },
}
