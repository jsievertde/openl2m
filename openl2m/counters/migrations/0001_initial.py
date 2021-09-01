# Generated by Django 3.2.6 on 2021-08-31 23:41

from django.db import migrations, models

from counters.models import Counter


def add_default_counters(apps, schema_editor):
    # add a few default counters to live throughout the app lifetime.
    c = Counter()
    c.name = "logins"
    c.description = "Number of logins"
    c.save()

    c = Counter()
    c.name = "logins_failed"
    c.description = "Number of failed logins"
    c.save()

    c = Counter()
    c.name = "changes"
    c.description = "Number of changes applied"
    c.save()

    c = Counter()
    c.name = "bulkedits"
    c.description = "Number of bulk edits"
    c.save()

    c = Counter()
    c.name = "errors"
    c.description = "Number of errors"
    c.save()

    c = Counter()
    c.name = "warnings"
    c.description = "Number of warnings"
    c.save()

    c = Counter()
    c.name = "access_denied"
    c.description = "Number of access denieds"
    c.save()

    c = Counter()
    c.name = "commands"
    c.description = "Number of commands ran"
    c.save()

    c = Counter()
    c.name = "views"
    c.description = "Number of views"
    c.save()

    c = Counter()
    c.name = "detailviews"
    c.description = "Number of detailed views"
    c.save()

    c = Counter()
    c.name = "hwinfo"
    c.description = "Number of hardware info views"
    c.save()


def remove_default_counters(apps, schema_editor):
    # and remove them if you want to migrate backwards
    pass


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Counter',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=64, unique=True)),
                ('description', models.CharField(blank=True, max_length=100)),
                ('value', models.PositiveBigIntegerField(default=0, verbose_name='Value of this counter')),
            ],
            options={
                'verbose_name': 'Counter',
                'verbose_name_plural': 'Counters',
                'ordering': ['name'],
            },
        ),
        migrations.RunPython(add_default_counters, remove_default_counters)
    ]
