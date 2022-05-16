from django.db import migrations
import uuid

def gen_team(apps, schema_editor):
    Batch = apps.get_model('core', 'Batch')
    BatchTeam = apps.get_model('core', 'BatchTeam')
    for batch in Batch.objects.all():
        if not batch.team:
            team = BatchTeam(
                owner = batch.owner
            )
            team.save()
            batch.team = team
            batch.save()

class Migration(migrations.Migration):

    dependencies = [
        ('core', '0022_auto_20220516_1025'),
    ]

    operations = [
        migrations.RunPython(gen_team, reverse_code=migrations.RunPython.noop),
    ]
