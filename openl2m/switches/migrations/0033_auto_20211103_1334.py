# Generated by Django 3.2.8 on 2021-11-03 20:34

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('switches', '0032_switchgroup_allow_all_vlans'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='netmikoprofile',
            options={'ordering': ['name'], 'verbose_name': 'Credentials Profile', 'verbose_name_plural': 'Credentials Profiles'},
        ),
        migrations.AlterField(
            model_name='netmikoprofile',
            name='verify_hostkey',
            field=models.BooleanField(default=False, verbose_name='Verify the host key'),
        ),
        migrations.AlterField(
            model_name='switch',
            name='connector_type',
            field=models.PositiveSmallIntegerField(choices=[[0, 'SNMP'], [1, 'Aruba AOS-CX'], [98, 'Commands Only'], [99, 'Napalm'], [100, 'Test Dummy']], default=0, help_text='How we connect to this device.', verbose_name='Connector Type'),
        ),
        migrations.AlterField(
            model_name='switch',
            name='netmiko_profile',
            field=models.ForeignKey(blank=True, help_text='The Credentials Profile has all the settings to access the switch via Netmiko/SSH/REST/API/Napalm.', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='netmiko_profile', to='switches.netmikoprofile', verbose_name='Credentials Profile'),
        ),
    ]