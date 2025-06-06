# Generated by Django 4.2.10 on 2025-01-22 18:55

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('smart_greenhouse_app', '0033_alter_environmentalsystem_unique_identifier_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='WindowControlSystem',
            fields=[
                ('environmentalsystem_ptr', models.OneToOneField(auto_created=True, on_delete=django.db.models.deletion.CASCADE, parent_link=True, primary_key=True, serialize=False, to='smart_greenhouse_app.environmentalsystem')),
                ('current_angle', models.FloatField(default=0.0, help_text='Current angle of the window system.')),
            ],
            bases=('smart_greenhouse_app.environmentalsystem',),
        ),
    ]
