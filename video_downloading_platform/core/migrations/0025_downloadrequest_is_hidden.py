# Generated by Django 3.1.13 on 2022-05-19 15:29

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0024_auto_20220519_1316'),
    ]

    operations = [
        migrations.AddField(
            model_name='downloadrequest',
            name='is_hidden',
            field=models.BooleanField(default=False),
        ),
    ]
