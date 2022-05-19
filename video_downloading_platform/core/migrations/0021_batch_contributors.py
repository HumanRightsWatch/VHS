# Generated by Django 3.1.13 on 2022-05-16 09:58

from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('core', '0020_auto_20220415_1948'),
    ]

    operations = [
        migrations.AddField(
            model_name='batch',
            name='contributors',
            field=models.ManyToManyField(help_text='List of contributors', related_name='batches_shared_with_me', to=settings.AUTH_USER_MODEL),
        ),
    ]