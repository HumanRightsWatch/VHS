# Generated by Django 3.1.13 on 2022-05-19 13:16

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('core', '0023_default_team'),
    ]

    operations = [
        migrations.AlterField(
            model_name='batch',
            name='team',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, related_name='batch', to='core.batchteam'),
        ),
        migrations.AlterField(
            model_name='batchteam',
            name='contributors',
            field=models.ManyToManyField(related_name='teams', to=settings.AUTH_USER_MODEL),
        ),
    ]
