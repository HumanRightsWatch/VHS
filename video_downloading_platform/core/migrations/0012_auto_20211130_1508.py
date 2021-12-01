# Generated by Django 3.1.13 on 2021-11-30 15:08

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0011_downloadedcontent_mime_type'),
    ]

    operations = [
        migrations.AlterField(
            model_name='batch',
            name='status',
            field=models.CharField(choices=[('OPEN', 'Open'), ('CLOSED', 'Closed'), ('ARCHIVED', 'Archived')], default='OPEN', max_length=16),
        ),
    ]
