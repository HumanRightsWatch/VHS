# Generated by Django 3.1.13 on 2022-10-10 13:09

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('core', '0031_auto_20220829_1541'),
    ]

    operations = [
        migrations.CreateModel(
            name='UploadRequest',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('eof', models.BooleanField(default=False)),
                ('md5', models.CharField(blank=True, max_length=32, null=True)),
                ('sha1', models.CharField(blank=True, max_length=64, null=True)),
                ('sha256', models.CharField(blank=True, max_length=64, null=True)),
                ('mime_type', models.CharField(blank=True, max_length=64, null=True)),
                ('name', models.CharField(blank=True, max_length=512, null=True)),
                ('size', models.IntegerField(default=0)),
                ('start_addr', models.IntegerField(default=0)),
                ('owner', models.ForeignKey(editable=False, on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]