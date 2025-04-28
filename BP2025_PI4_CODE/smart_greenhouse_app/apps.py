from django.apps import AppConfig
from django.core.signals import request_started
from django.dispatch import receiver
from django.conf import settings



class SmartGreenhouseAppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'smart_greenhouse_app'
