from django.core.management.base import BaseCommand

from Global.models import Dokument2


class Command(BaseCommand):
    help = 'Erzeugt fehlende Vorschaubilder (Standbild per ffmpeg) für Video-Dokumente.'

    def handle(self, *args, **options):
        created, failed = 0, 0
        for dokument in Dokument2.objects.exclude(dokument='').exclude(dokument=None).iterator():
            try:
                if not dokument.get_document_type().startswith('video'):
                    continue
                path = dokument.get_preview_converted()
            except Exception as e:
                path = None
                self.stderr.write(f'{dokument.pk}: {e}')
            if path:
                created += 1
                self.stdout.write(f'{dokument.pk}: {path}')
            else:
                failed += 1
                self.stderr.write(f'{dokument.pk}: keine Vorschau erzeugt ({dokument.dokument.name})')
        self.stdout.write(self.style.SUCCESS(f'{created} Vorschaubilder vorhanden/erzeugt, {failed} fehlgeschlagen'))
