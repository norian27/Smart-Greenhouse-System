"""
Django views for managing sensor units, greenhouses, and environmental systems.

This module includes views that handle HTTP requests to manage sensor units, greenhouses,
and environmental systems.

Each view interacts with the model via Django's ORM to retrieve, update, or delete data, and then returns HTTP responses or renders templates with context data.
"""

from django.http import JsonResponse, HttpResponse, HttpResponseRedirect
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import render, redirect, get_object_or_404
from .forms import EnvironmentalSystemSettingsForm, GreenhouseForm, SensorUnitForm, ConfirmRegistrationForm, EnvironmentalSystemForm
from .models import SensorUnit, Greenhouse, PendingSensorRegistration, Alert, WeatherForecast, EnvironmentalSystem, WindowControlSystem
from django.utils.timezone import now, timezone
from django.urls import reverse
from datetime import datetime, timedelta
from django.contrib import messages
from django.test import RequestFactory
from django.db import transaction
from mqtt_communication import publish_control_command


import paho.mqtt.publish as publish
import ssl



import json
import os
import logging

logger = logging.getLogger(__name__)


def get_sensor_data(request):
    """
    Retrieves data for all sensor units and returns it in JSON format.
    
    Parameters:
        request (HttpRequest): The HTTP request object.
    
    Returns:
        JsonResponse: Contains sensor data including identifiers, online status, and last recorded data.
    """
    sensors = SensorUnit.objects.all()
    data = {
        sensor.id: {
            'identifier': sensor.identifier,
            'is_online': sensor.is_online(),
            'last_data': sensor.get_last_data()
        } for sensor in sensors
    }
    return JsonResponse(data)

def pending_registrations(request):
    """
    Displays a list of pending sensor unit registrations.
    
    Parameters:
        request (HttpRequest): The HTTP request object.
    
    Returns:
        HttpResponse: Renders the pending registrations page with the list of registrations.
    """
    logger.debug("Entering pending_registrations function")
    pending_registrations = PendingSensorRegistration.objects.all()
    return render(request, 'pending_registrations.html', {'pending_registrations': pending_registrations})

def confirm_registration(request, id):
    """
    Confirms a pending registration as either a Sensor Unit or an Environmental System.

    Parameters:
        request (HttpRequest): The HTTP request object.
        id (int): The ID of the PendingSensorRegistration to confirm.

    Returns:
        HttpResponse: Renders the confirmation form for GET requests, or redirects to the pending registrations page upon successful POST.
    """
    logger.debug("Entering confirm_registration function")
    pending_registration = get_object_or_404(PendingSensorRegistration, pk=id)

    if request.method == 'POST':
        form = ConfirmRegistrationForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                registration_type = form.cleaned_data['registration_type']

                if registration_type == 'sensor':
                    sensor_unit = SensorUnit(
                        greenhouse=form.cleaned_data['greenhouse'],
                        unique_identifier=pending_registration.unique_identifier,
                        identifier=form.cleaned_data['identifier'],
                        data_frequency=form.cleaned_data['data_frequency'],
                        sensor_type=form.cleaned_data['sensor_type']
                    )
                    sensor_unit.save()

                    sensor_unit.manage_thresholds()

                elif registration_type == 'system':
                    env_system = EnvironmentalSystem(
                        greenhouse=form.cleaned_data['greenhouse'],
                        unique_identifier=pending_registration.unique_identifier,
                        name=form.cleaned_data['name'],
                        env_type=form.cleaned_data['env_type'],
                        target_value=form.cleaned_data['target_value'],
                        identifier=form.cleaned_data['name']
                    )
                    env_system.save()

                pending_registration.delete()
                return redirect('pending_registrations')
        else:
            logger.warning("Form is not valid")
    else:
        form = ConfirmRegistrationForm(initial={'unique_identifier': pending_registration.unique_identifier})

    return render(request, 'confirm_registration.html', {'form': form, 'id': id})


def list_greenhouses(request):
    """
    Displays a list of all greenhouses registered in the system.
    
    Parameters:
        request (HttpRequest): The HTTP request object.
    
    Returns:
        HttpResponse: Renders the list of greenhouses to the user.
    """
    logger.debug("Entering list_greenhouses function")

    greenhouses = Greenhouse.objects.all()
    return render(request, 'list_greenhouses.html', {'greenhouses': greenhouses})

def greenhouse_detail(request, pk):
    """
    Provides the details of a specific greenhouse, allows update to environmental systems' target values through POST requests.
    
    Parameters:
        request (HttpRequest): The HTTP request object.
        pk (int): Primary key of the greenhouse to display.
    
    Returns:
        HttpResponse: Redirects after updates or renders details of a specific greenhouse.
    """
    greenhouse = get_object_or_404(Greenhouse, pk=pk)
    if request.method == 'POST' and 'update_system' in request.POST:
        system_id = request.POST.get('system_id')
        new_target_value = request.POST.get('target_value')
        system = EnvironmentalSystem.objects.get(pk=system_id)
        system.target_value = new_target_value
        system.save()
        messages.success(request, f"Updated {system.name}'s target value to {new_target_value}.")
        return HttpResponseRedirect(reverse('greenhouse_detail', args=[pk]))

    return render(request, 'greenhouse_detail.html', {
        'greenhouse': greenhouse,
        'sensors': greenhouse.sensors.all(),
        'env_systems': greenhouse.env_systems.all(),
    })


def add_greenhouse(request):
    """
    Adds a new greenhouse using a form submission. If the form is valid, the greenhouse is saved and the user is redirected to the list of greenhouses.
    
    Parameters:
        request (HttpRequest): The HTTP request object.
    
    Returns:
        HttpResponse: Redirects to list of greenhouses after successful submission or renders the form again if validation fails.
    """
    logger.debug("Entering add_greenhouse function")

    if request.method == 'POST':
        form = GreenhouseForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('list_greenhouses')
    else:
        form = GreenhouseForm()
    return render(request, 'add_greenhouse.html', {'form': form})

def add_sensor_unit(request):
    """
    Adds a new sensor unit to a greenhouse via a form submission. Validates and saves the sensor unit if the form is valid.
    
    Parameters:
        request (HttpRequest): The HTTP request object.
    
    Returns:
        HttpResponse: Redirects to the list of greenhouses after saving or renders the form again for corrections.
    """
    logger.debug("Entering add_sensor_unit function")

    if request.method == 'POST':
        form = SensorUnitForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('list_greenhouses')
    else:
        form = SensorUnitForm()
    return render(request, 'add_sensor_unit.html', {'form': form})

def add_environmental_system(request):
    """
    Adds a new environmental system to the database via a form submission, validating and saving the system if the form is valid.
    
    Parameters:
        request (HttpRequest): The HTTP request object.
    
    Returns:
        HttpResponse: Redirects to list of greenhouses after successful addition or renders the form again if necessary.
    """
    if request.method == 'POST':
        form = EnvironmentalSystemForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Environmental system added successfully.')
            return redirect('list_greenhouses')
    else:
        form = EnvironmentalSystemForm()
    return render(request, 'add_environmental_system.html', {'form': form})

def toggle_automation(request, pk):
    """
    Toggles the automation status of a greenhouse.

    Parameters:
        request (HttpRequest): The HTTP request object.
        pk (int): Primary key of the greenhouse for which to toggle automation.

    Returns:
        HttpResponse: Redirects to the greenhouse detail view after changing the automation status.
    """
    greenhouse = get_object_or_404(Greenhouse, pk=pk)
    if request.method == 'POST':
        greenhouse.automated = not greenhouse.automated
        greenhouse.save()
        return redirect('greenhouse_detail', pk=pk)

def edit_environmental_system(request, system_id):
    """
    Edits an environmental system's settings via a form submission.

    Parameters:
        request (HttpRequest): The HTTP request object.
        system_id (int): Primary key of the environmental system to edit.

    Returns:
        HttpResponse: Redirects to the greenhouse detail view after successful update or renders the form again with errors.
    """
    system = get_object_or_404(EnvironmentalSystem, pk=system_id)
    if request.method == 'POST':
        form = EnvironmentalSystemForm(request.POST, instance=system)
        if form.is_valid():
            form.save()
            messages.success(request, 'System updated successfully.')
            return redirect('greenhouse_detail', pk=system.greenhouse.pk)
    else:
        form = EnvironmentalSystemForm(instance=system)
    return render(request, 'edit_environmental_system.html', {'form': form, 'system': system})

@csrf_exempt
def toggle_environmental_system(request, system_id):
    """
    Toggles the active state of an environmental system via MQTT and updates the system's status in the database.

    Parameters:
        request (HttpRequest): The HTTP request object.
        system_id (int): Primary key of the environmental system to toggle.

    Returns:
        JsonResponse: Indicates the success or failure of the operation along with the new state of the system.
    """
    logger.debug("Toggling system state")

    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Method not allowed'}, status=405)

    system = get_object_or_404(EnvironmentalSystem, pk=system_id)
    action = request.POST.get('action')

    try:
        if system.env_type == 'Window':
            window_system = get_object_or_404(WindowControlSystem, pk=system_id)
            angle = float(request.POST.get('angle', window_system.current_angle))

            if action in ['activate', 'adjust']:
                logger.debug(f"Incoming angle in POST: {request.POST.get('angle')}")
                window_system.adjust_angle(angle)
                window_system.activate()
            elif action == 'deactivate':
                window_system.deactivate()
            else:
                return JsonResponse({'status': 'error', 'message': 'Invalid action for window system'}, status=400)

            window_system.save()
            window_system.refresh_from_db()
            publish_control_command(window_system, action)

        else:
            if action == 'activate':
                system.activate()
            elif action == 'deactivate':
                system.deactivate()
            else:
                return JsonResponse({'status': 'error', 'message': 'Invalid action'}, status=400)

            system.save()
            system.refresh_from_db()

            publish_control_command(system, action)

        system.refresh_from_db()

        return JsonResponse({'status': 'success', 'system_active': system.is_active})

    except Exception as e:
        logger.error(f"Failed to toggle environmental system: {e}")
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
    
@csrf_exempt
def reset_sprinkler(request, pk):
    """
    Sends a reset command to a sprinkler system via MQTT.

    Parameters:
        request (HttpRequest): The HTTP request object.
        pk (int): Primary key of the sprinkler environmental system to reset.

    Returns:
        JsonResponse: Status of the reset operation.
    """
    if request.method == "POST":
        try:
            env_system = EnvironmentalSystem.objects.get(pk=pk)
            if env_system.env_type != "Sprinkler":
                return JsonResponse({"status": "error", "message": "Not a sprinkler system."}, status=400)
            
            publish_control_command(env_system, "reset")
            return JsonResponse({"status": "success", "message": "Reset command sent."})
        except EnvironmentalSystem.DoesNotExist:
            return JsonResponse({"status": "error", "message": "System not found."}, status=404)
    return JsonResponse


def delete_environmental_system(request, system_id):
    """
    Deletes an environmental system from the database.

    Parameters:
        request (HttpRequest): The HTTP request object.
        system_id (int): Primary key of the environmental system to delete.

    Returns:
        HttpResponse: Redirects to the greenhouse detail view after successfully removing the system.
    """

    system = get_object_or_404(EnvironmentalSystem, pk=system_id)
    greenhouse_id = system.greenhouse.pk
    system.delete()
    messages.success(request, 'System removed successfully.')
    return redirect('greenhouse_detail', pk=greenhouse_id)


def index(request):
    """
    Displays the index page showing recent alerts and forecasts.

    Parameters:
        request (HttpRequest): The HTTP request object.

    Returns:
        HttpResponse: Renders the index page with lists of recent alerts and weather forecasts.
    """

    logger.debug("Entering index function")

    recent_alerts = Alert.objects.filter(is_active=True).order_by('-timestamp')[:10]
    recent_forecasts = WeatherForecast.objects.order_by('-forecast_date')[:4]

    return render(request, 'index.html', {
        'recent_alerts': recent_alerts,
        'recent_forecasts': recent_forecasts
    })


def delete_sensor_unit(request, sensor_id):
    """
    Deletes a sensor unit from the database.

    Parameters:
        request (HttpRequest): The HTTP request object.
        sensor_id (int): ID of the sensor unit to delete.

    Returns:
        HttpResponse: Redirects to the list of greenhouses after the sensor is deleted.
    """
    logger.debug("Entering delete_sensor_unit function")

    sensor = get_object_or_404(SensorUnit, id=sensor_id)
    if request.method == 'POST':
        sensor.delete()
        return redirect(reverse('greenhouse_detail', args=[sensor.greenhouse.id]))
    return render(request, 'sensor_confirm_delete.html', {'sensor': sensor})

def edit_sensor_unit(request, sensor_id):
    """
    Edits a sensor unit's details via a form submission.

    Parameters:
        request (HttpRequest): The HTTP request object.
        sensor_id (int): ID of the sensor unit to edit.

    Returns:
        HttpResponse: Redirects to the greenhouse detail view after successful update or renders the form again with errors.
    """
    sensor = get_object_or_404(SensorUnit, id=sensor_id)
    
    
    if request.method == 'POST':
        form = SensorUnitForm(request.POST, instance=sensor)
        if form.is_valid():
            form.save()
            return redirect('greenhouse_detail', pk=sensor.greenhouse.id)  # Redirect after save
    else:
        form = SensorUnitForm(instance=sensor)
    
    return render(request, 'edit_sensor_unit.html', {'form': form, 'sensor': sensor})

def resolve_alert(request, alert_id):
    """
    Marks an alert as resolved.

    Parameters:
        request (HttpRequest): The HTTP request object.
        alert_id (int): ID of the alert to resolve.

    Returns:
        HttpResponse: Redirects to the sensor alerts log page after the alert is marked as resolved.
    """

    logger.debug("Entering resolve_alert function")

    if request.method == "POST":
        alert = get_object_or_404(Alert, pk=alert_id)
        alert.is_active = False
        alert.resolved_timestamp = now()
        alert.save()
        return redirect('sensor_alerts_log', sensor_id=alert.sensor.id)

def sensor_alerts_log(request, sensor_id):
    """
    Displays a log of all alerts for a particular sensor.

    Parameters:
        request (HttpRequest): The HTTP request object.
        sensor_id (int): ID of the sensor whose alerts are to be displayed.

    Returns:
        HttpResponse: Renders the sensor alerts log page with the list of alerts.
    """
    logger.debug("Entering sensor_alerts_log function")

    sensor = get_object_or_404(SensorUnit, pk=sensor_id)
    alerts = sensor.alerts.all().order_by('-timestamp')
    return render(request, 'sensor_alerts_log.html', {'sensor': sensor, 'alerts': alerts})

def edit_greenhouse(request, pk):
    """
    Edits details of a greenhouse via a form submission.

    Parameters:
        request (HttpRequest): The HTTP request object.
        pk (int): Primary key of the greenhouse to edit.

    Returns:
        HttpResponse: Redirects to the greenhouse detail view after successful update or renders the form again with errors.
    """
    logger.debug("Entering edit_greenhouse function")

    greenhouse = get_object_or_404(Greenhouse, pk=pk)
    if request.method == 'POST':
        form = GreenhouseForm(request.POST, instance=greenhouse)
        if form.is_valid():
            form.save()
            return redirect('greenhouse_detail', pk=greenhouse.pk)
    else:
        form = GreenhouseForm(instance=greenhouse)
    return render(request, 'edit_greenhouse.html', {'form': form, 'greenhouse': greenhouse})

 

def delete_greenhouse(request, pk):
    """
    Deletes a greenhouse from the database.

    Parameters:
        request (HttpRequest): The HTTP request object.
        pk (int): Primary key of the greenhouse to delete.

    Returns:
        HttpResponse: Redirects to the list of greenhouses after successful deletion.
    """
    greenhouse = get_object_or_404(Greenhouse, pk=pk)
    if request.method == 'POST':
        greenhouse.delete()
        return redirect('list_greenhouses')
    return render(request, 'greenhouse_confirm_delete.html', {'greenhouse': greenhouse})

 

def adjust_window_angle(request, pk):
    """
    Adjusts the angle of a window control system.

    Parameters:
        request (HttpRequest): The HTTP request object.
        pk (int): Primary key of the window control system.

    Returns:
        JsonResponse: Indicates the success or failure of the angle adjustment.
    """
    if request.method == 'POST':
        try:
            new_angle = float(request.POST.get('angle', 0))
            window_system = get_object_or_404(WindowControlSystem, pk=pk)
            window_system.adjust_angle(new_angle)
            return JsonResponse({'status': 'success', 'new_angle': new_angle})
        except ValueError:
            return JsonResponse({'status': 'error', 'message': 'Invalid angle value'}, status=400)
    return JsonResponse({'status': 'error', 'message': 'Method not allowed'}, status=405)
