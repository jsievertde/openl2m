# Generated by Django 3.2.6 on 2021-08-30 20:48

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('switches', '0024_auto_20210823_1007'),
    ]

    operations = [
        migrations.AlterField(
            model_name='switch',
            name='connector_type',
            field=models.PositiveSmallIntegerField(choices=[[0, 'SNMP'], [1, 'Napalm'], [2, 'Aruba AOS-CX']], default=0, help_text='How we connect to this device.', verbose_name='Connector Type'),
        ),
    ]
