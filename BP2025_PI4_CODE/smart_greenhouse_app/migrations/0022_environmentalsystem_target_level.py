# Generated by Django 4.2.10 on 2024-04-27 13:17

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('smart_greenhouse_app', '0021_greenhouse_automated_environmentalsystem'),
    ]

    operations = [
        migrations.AddField(
            model_name='environmentalsystem',
            name='target_level',
            field=models.FloatField(default=0.0),
        ),
    ]
