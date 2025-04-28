from django.urls import re_path
from .consumers import EnvSystemConsumer, SensorDataConsumer

websocket_urlpatterns = [
    re_path(r"ws/env_system/(?P<system_id>[\w:-]+)/$", EnvSystemConsumer.as_asgi()),
        re_path(r'ws/sensors/$', SensorDataConsumer.as_asgi()),

]
