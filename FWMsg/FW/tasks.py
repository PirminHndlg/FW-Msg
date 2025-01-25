from datetime import datetime, timedelta
from django.db.models import Q
from celery import shared_task

from FW.models import FreiwilligerAufgaben

from Global.send_email import send_mail_smtp


@shared_task
def send_aufgaben_email_task():
    faellige_aufgaben = FreiwilligerAufgaben.objects.filter(
        erledigt=False,
        pending=False,
        faellig__lt=datetime.now(),
    )#.filter(
     #   Q(last_reminder__lt=datetime.now() - timedelta(days=14)) | Q(last_reminder__isnull=True)
    #)

    # faellige_aufgaben = faellige_aufgaben.filter(
    #     Q(last_reminder__lt=datetime.now() - timedelta(days=14)) | Q(last_reminder__isnull=True)
    # )

    # faellige_aufgaben = faellige_aufgaben.filter(
    #     faellig__lt=datetime.now() - timedelta(days=14)
    # )

    for aufgabe in faellige_aufgaben:
        send_mail_smtp('test@p0k.de', 'test', f'<h1>test</h1><p>{aufgabe.aufgabe.name}</p><p>{aufgabe.freiwilliger}</p>')
        aufgabe.last_reminder = datetime.now()
        aufgabe.save()

    return len(faellige_aufgaben)
