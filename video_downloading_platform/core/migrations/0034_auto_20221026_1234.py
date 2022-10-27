# Generated by Django 3.1.13 on 2022-10-26 12:34

from django.db import migrations, models
import video_downloading_platform.core.models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0033_uploadrequest_content'),
    ]

    operations = [
        migrations.AddField(
            model_name='uploadrequest',
            name='chunks',
            field=models.JSONField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='uploadrequest',
            name='content',
            field=models.FileField(blank=True, max_length=512, null=True, upload_to=video_downloading_platform.core.models._get_upload_dir),
        ),
    ]
