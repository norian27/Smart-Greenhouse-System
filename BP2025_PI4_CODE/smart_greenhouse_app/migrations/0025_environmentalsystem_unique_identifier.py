# Generated by Django 4.2.10 on 2024-04-27 19:40

from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('smart_greenhouse_app', '0024_soilmoisturethreshold'),
    ]

    operations = [
        migrations.AddField(
            model_name='environmentalsystem',
            name='unique_identifier',
            field=models.CharField(default=django.utils.timezone.now, max_length=255, unique=True),
            preserve_default=False,
        ),
    ]
