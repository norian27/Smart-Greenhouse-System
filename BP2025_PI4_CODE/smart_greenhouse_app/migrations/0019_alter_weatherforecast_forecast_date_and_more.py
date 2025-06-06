# Generated by Django 4.2.10 on 2024-04-14 22:45

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('smart_greenhouse_app', '0018_alter_weatherforecast_options_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='weatherforecast',
            name='forecast_date',
            field=models.DateField(),
        ),
        migrations.AlterField(
            model_name='weatherforecast',
            name='minimum_temperature',
            field=models.FloatField(),
        ),
    ]
