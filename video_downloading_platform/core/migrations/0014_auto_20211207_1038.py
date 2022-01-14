# Generated by Django 3.1.13 on 2021-12-07 10:38

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid
import video_downloading_platform.core.models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('core', '0013_downloadreport_archive'),
    ]

    operations = [
        migrations.AlterField(
            model_name='batch',
            name='created_at',
            field=models.DateTimeField(auto_now_add=True, help_text='Creation date of your collection.'),
        ),
        migrations.AlterField(
            model_name='batch',
            name='id',
            field=models.UUIDField(default=uuid.uuid4, editable=False, help_text='Unique identifier of your collection.', primary_key=True, serialize=False),
        ),
        migrations.AlterField(
            model_name='batch',
            name='name',
            field=models.CharField(default=video_downloading_platform.core.models._generate_random_name, help_text='Give a meaningful name to your collection.', max_length=512),
        ),
        migrations.AlterField(
            model_name='batch',
            name='owner',
            field=models.ForeignKey(editable=False, help_text='Who owns the current collection.', on_delete=django.db.models.deletion.CASCADE, related_name='my_batches', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AlterField(
            model_name='batch',
            name='updated_at',
            field=models.DateTimeField(auto_now=True, help_text='Latest modification of your collection.'),
        ),
    ]