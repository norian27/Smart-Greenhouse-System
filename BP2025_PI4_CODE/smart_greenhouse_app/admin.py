"""
Admin configuration for the Django application models.

This module configures how models are represented in the Django admin interface,
including list displays, readonly fields, and custom methods for display in the admin.

Models registered are SensorUnit, Greenhouse, Alert, PendingSensorRegistration,
TemperatureThreshold, HumidityThreshold, WeatherForecast, and EnvironmentalSystem.
"""
from django.contrib import admin
from .models import SensorUnit, Greenhouse, Alert, PendingSensorRegistration, SensorThreshold, EnvironmentalSystem, WindowControlSystem
admin.site.register(Greenhouse)

@admin.register(SensorUnit)
class SensorUnitAdmin(admin.ModelAdmin):
    """
    Admin interface for SensorUnit.

    Attributes:
        list_display (tuple): Fields to display in the admin list view.
        readonly_fields (tuple): Fields that are readonly in the admin form.
    """
    list_display = ('identifier', 'unique_identifier', 'is_update_pending', 'last_check_in')
    readonly_fields = ('settings_updated_display',)

    def is_update_pending(self, obj):
        """
        Determines if an update is pending for the sensor unit.

        Parameters:
            obj (SensorUnit): The SensorUnit instance.

        Returns:
            bool: True if settings update is pending, False otherwise.
        """
        return obj.settings_updated
    is_update_pending.boolean = True
    is_update_pending.short_description = 'Update Pending'

    def settings_updated_display(self, obj):
        """
        Display whether the settings have been updated for the sensor unit.
        Parameters:
            obj (SensorUnit): The SensorUnit instance.
        Returns:
            bool: True if settings have been updated, False otherwise.
        """
        return obj.settings_updated
    settings_updated_display.boolean = True
    settings_updated_display.short_description = 'Update Pending'

class SensorThresholdAdmin(admin.ModelAdmin):
    """
    Admin interface for SensorThreshold.

    Attributes:
        list_display (tuple): Fields to display in the admin list view.
        search_fields (list): Fields to search within the admin interface.
    """
    list_display = ('sensor', 'key', 'threshold_low', 'threshold_high')
    search_fields = ['sensor__identifier', 'key']



# Register other models with the admin site
admin.site.register(Alert)
admin.site.register(PendingSensorRegistration)
admin.site.register(SensorThreshold, SensorThresholdAdmin)
admin.site.register(EnvironmentalSystem)
admin.site.register(WindowControlSystem)