"""
Django forms for managing user input and validation.

This module defines Django forms used for collecting and validating user input in various parts of the application.
Forms are provided for tasks such as user registration, login, data entry, and other interactions with the application.
"""

from django import forms
from django.db import transaction
from .models import Greenhouse, SensorUnit,EnvironmentalSystem, SensorThreshold


class GreenhouseForm(forms.ModelForm):
    """
    Form for creating or updating a greenhouse.

    Attributes:
        Meta (class): Inner class containing metadata for the form.
            model (Model): The model associated with the form.
            fields (list): The fields to include in the form.
            widgets (dict): Custom widgets to use for form fields.
    """
    class Meta:
        """
        Metadata for the GreenhouseForm.

        Specifies the model, fields, and widgets for the form.
        """
        model = Greenhouse # The model associated with the form
        fields = ['name', 'location', 'contents']# The fields to include in the form
        # Custom widgets for form fields
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'location': forms.TextInput(attrs={'class': 'form-control'}),
            'contents': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

class SensorUnitForm(forms.ModelForm):
    """
    Form for creating or updating a sensor unit.

    Allows setting thresholds for humidity, temperature, and soil moisture.

    Attributes:
        Meta (class): Inner class containing metadata for the form.
            model (Model): The model associated with the form.
            fields (list): The fields to include in the form.
    """
    temperature_threshold_low = forms.FloatField(required=False)
    temperature_threshold_high = forms.FloatField(required=False)
    humidity_threshold_low = forms.FloatField(required=False)
    humidity_threshold_high = forms.FloatField(required=False)
    soil_moisture_threshold_low = forms.FloatField(required=False)
    soil_moisture_threshold_high = forms.FloatField(required=False)

    class Meta:
        model = SensorUnit
        fields = ['identifier', 'greenhouse', 'data_frequency']

    def __init__(self, *args, **kwargs):
        """
        Initializes a new instance of the SensorUnitForm.

        Sets initial threshold values based on existing sensor data if available.

        Parameters:
            *args: Variable-length argument list.
            **kwargs: Arbitrary keyword arguments.
        """
        super().__init__(*args, **kwargs)
        instance = kwargs.get('instance')
        if instance:
            last_data = instance.get_last_data()
    
            sensor_types = []
            for key in ['humidity', 'temperature', 'soil_moisture']:
                if key in last_data:
                    sensor_types.append(key)
                    threshold = instance.thresholds.filter(key=key).first()
                    if threshold:
                        self.fields[f"{key}_threshold_low"].initial = threshold.threshold_low
                        self.fields[f"{key}_threshold_high"].initial = threshold.threshold_high
                    else:
                        self.fields[f"{key}_threshold_low"].initial = 0
                        self.fields[f"{key}_threshold_high"].initial = 100
    
            instance.sensor_type = ' '.join(sensor_types)
    

    def save(self, commit=True):
        """
        Saves the sensor unit instance and updates its thresholds based on form input.

        Parameters:
            commit (bool): Flag indicating whether to immediately save to the database.

        Returns:
            SensorUnit: The saved sensor unit instance.
        """
        instance = super().save(commit)

        instance.update_settings(data_frequency=instance.data_frequency)


        last_data = instance.get_last_data()
        valid_keys = last_data.keys()

        for key in valid_keys:
            if key in ['humidity', 'temperature', 'soil_moisture']:
                low_field = f"{key}_threshold_low"
                high_field = f"{key}_threshold_high"

                # Only update thresholds if both fields are provided
                low_value = self.cleaned_data.get(low_field)
                high_value = self.cleaned_data.get(high_field)

                if low_value is not None and high_value is not None:
                    SensorThreshold.objects.update_or_create(
                        sensor=instance,
                        key=key,
                        defaults={
                            'threshold_low': low_value,
                            'threshold_high': high_value
                        }
                    )

        instance.thresholds.exclude(key__in=valid_keys).delete()
        return instance



class ConfirmRegistrationForm(forms.Form):
    """
    Form for confirming the registration of a Sensor Unit or an Environmental System.

    Fields:
        registration_type (ChoiceField): Selects the type of registration ('sensor' or 'system').
        identifier (CharField): Identifier for the sensor unit (required if registering a sensor).
        data_frequency (IntegerField): Data sending frequency in seconds (required if registering a sensor).
        sensor_type (CharField): Type of the sensor data (optional).
        temperature_threshold_low (FloatField): Lower temperature alert threshold (optional).
        temperature_threshold_high (FloatField): Upper temperature alert threshold (optional).
        humidity_threshold_low (FloatField): Lower humidity alert threshold (optional).
        humidity_threshold_high (FloatField): Upper humidity alert threshold (optional).
        name (CharField): Name of the environmental system (required if registering a system).
        env_type (ChoiceField): Type of environmental system (required if registering a system).
        target_value (FloatField): Target value for the environmental system (required if registering a system).
        greenhouse (ModelChoiceField): The greenhouse associated with the registration.

    Methods:
        clean(): Validates required fields based on the selected registration type.
    """
    REGISTRATION_TYPE_CHOICES = [
        ('sensor', 'Sensor Unit'),
        ('system', 'Environmental System')
    ]

    registration_type = forms.ChoiceField(choices=REGISTRATION_TYPE_CHOICES, required=True, widget=forms.Select(attrs={'class': 'form-control'}))

    identifier = forms.CharField(required=False)
    data_frequency = forms.IntegerField(required=False)
    sensor_type = forms.CharField(required=False)
    temperature_threshold_low = forms.FloatField(required=False)
    temperature_threshold_high = forms.FloatField(required=False)
    humidity_threshold_low = forms.FloatField(required=False)
    humidity_threshold_high = forms.FloatField(required=False)

    name = forms.CharField(required=False)
    env_type = forms.ChoiceField(choices=EnvironmentalSystem.SystemType.choices, required=False)
    target_value = forms.FloatField(required=False)

    greenhouse = forms.ModelChoiceField(queryset=Greenhouse.objects.all(), required=True)

    def clean(self):
        cleaned_data = super().clean()
        registration_type = cleaned_data.get('registration_type')

        if registration_type == 'sensor':
            if not cleaned_data.get('identifier'):
                self.add_error('identifier', 'This field is required for sensor registration.')
            if not cleaned_data.get('data_frequency'):
                self.add_error('data_frequency', 'This field is required for sensor registration.')
        elif registration_type == 'system':
            if not cleaned_data.get('name'):
                self.add_error('name', 'This field is required for environmental system registration.')
            if not cleaned_data.get('env_type'):
                self.add_error('env_type', 'This field is required for environmental system registration.')
            if cleaned_data.get('target_value') is None:
                self.add_error('target_value', 'This field is required for environmental system registration.')

        return cleaned_data

class EnvironmentalSystemForm(forms.ModelForm):
    """
    Form for creating or updating environmental system settings.

    Attributes:
        Meta (class): Inner class containing metadata for the form.
            model (Model): The model associated with the form.
            fields (list): The fields to include in the form.
    """
    class Meta:
        """
        Metadata for the EnvironmentalSystemForm.

        Specifies the model and fields for the form.
        """
        model = EnvironmentalSystem
        fields = ['name', 'env_type', 'greenhouse', 'target_value']

    def __init__(self, *args, **kwargs):
        """
        Initializes a new instance of the EnvironmentalSystemForm.

        Sets the available greenhouses for the environmental system selection.

        Args:
            *args: Variable-length argument list.
            **kwargs: Arbitrary keyword arguments.
        """
        super(EnvironmentalSystemForm, self).__init__(*args, **kwargs)
        self.fields['greenhouse'].queryset = Greenhouse.objects.all()  # Allow choosing any greenhouse

class EnvironmentalSystemSettingsForm(forms.ModelForm):
    """
    Form for updating environmental system settings.

    Attributes:
        Meta (class): Inner class containing metadata for the form.
            model (Model): The model associated with the form.
            fields (list): The fields to include in the form.
    """
    class Meta:
        """
        Metadata for the EnvironmentalSystemSettingsForm.

        Specifies the model and fields for the form.
        """
        model = EnvironmentalSystem
        fields = ['name', 'env_type', 'target_value']
