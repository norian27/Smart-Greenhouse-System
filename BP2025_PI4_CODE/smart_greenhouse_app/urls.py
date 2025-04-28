"""
URL Routing configuration for the Django project.

This module defines URL paths for the Django application, linking each URL pattern to specific view functions.
These URL patterns facilitate navigation and functionality within the smart_greenhouse web application, supporting tasks dealing with objects in the system.

Each URL is named to allow for easy referencing in Django templates and view functions.
"""
from django.urls import path
from . import views

urlpatterns = [
    # Alert management
    path('alerts/resolve/<int:alert_id>/', views.resolve_alert, name='resolve_alert'),
    
    # Sensor unit management
    path('sensor/edit/<int:sensor_id>/', views.edit_sensor_unit, name='edit_sensor_unit'),
    path('sensors/add/', views.add_sensor_unit, name='add_sensor_unit'),
    path('sensor/delete/<int:sensor_id>/', views.delete_sensor_unit, name='delete_sensor_unit'),
    path('sensors/<int:sensor_id>/alerts/', views.sensor_alerts_log, name='sensor_alerts_log'),
   
    # Greenhouse management
    path('greenhouses/', views.list_greenhouses, name='list_greenhouses'),
    path('greenhouses/add/', views.add_greenhouse, name='add_greenhouse'),
    path('greenhouses/<int:pk>/', views.greenhouse_detail, name='greenhouse_detail'),
    path('greenhouses/edit/<int:pk>/', views.edit_greenhouse, name='edit_greenhouse'),
    path('greenhouse/delete/<int:pk>/', views.delete_greenhouse, name='delete_greenhouse'),
    path('greenhouses/<int:pk>/toggle_automation/', views.toggle_automation, name='toggle_automation'),    

    # Environmental system management
    path('systems/edit/<int:system_id>/', views.edit_environmental_system, name='edit_environmental_system'),
    path('systems/delete/<int:system_id>/', views.delete_environmental_system, name='delete_environmental_system'),
    path('systems/toggle/<int:system_id>/', views.toggle_environmental_system, name='toggle_environmental_system'),

    # System controls
    path('system/<slug:pk>/adjust_angle/', views.adjust_window_angle, name='adjust_window_angle'),
    path('system/<slug:pk>/reset/', views.reset_sprinkler, name='reset_sprinkler'),

    # API
    path('api/get-sensor-data/', views.get_sensor_data, name='get_sensor_data'),

    # Pending registrations
    path('pending_registrations/', views.pending_registrations, name='pending_registrations'),
    path('confirm-registration/<int:id>/', views.confirm_registration, name='confirm_registration'),

    # Home page
    path('', views.index, name='index'),

]
