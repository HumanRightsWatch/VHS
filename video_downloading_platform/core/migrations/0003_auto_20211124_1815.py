# Generated by Django 3.1.13 on 2021-11-24 18:15

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('core', '0002_auto_20211124_1737'),
    ]

    operations = [
        migrations.AlterField(
            model_name='batch',
            name='name',
            field=models.TextField(default='autumn-green-fanta-hydrogen', help_text='Give a meaningful name to your download batch. (Optional)', max_length=512),
        ),
        migrations.AlterField(
            model_name='batch',
            name='owner',
            field=models.ForeignKey(editable=False, help_text='Who owns the current download batch.', on_delete=django.db.models.deletion.CASCADE, related_name='my_batches', to=settings.AUTH_USER_MODEL),
        ),
    ]