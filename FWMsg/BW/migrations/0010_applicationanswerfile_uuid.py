import uuid
from django.db import migrations, models


def populate_uuids(apps, schema_editor):
    ApplicationAnswerFile = apps.get_model('BW', 'ApplicationAnswerFile')
    for obj in ApplicationAnswerFile.objects.filter(uuid__isnull=True):
        obj.uuid = uuid.uuid4()
        obj.save(update_fields=['uuid'])


class Migration(migrations.Migration):

    dependencies = [
        ('BW', '0009_applicationtext_person_cluster_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='applicationanswerfile',
            name='uuid',
            field=models.UUIDField(null=True, editable=False),
        ),
        migrations.RunPython(populate_uuids, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='applicationanswerfile',
            name='uuid',
            field=models.UUIDField(default=uuid.uuid4, editable=False, unique=True),
        ),
    ]
