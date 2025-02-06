import os

from django.conf import settings

from celery import Celery
from celery.schedules import crontab

from Global.send_email import send_aufgaben_email

from datetime import datetime, timedelta
from django.db.models import Q

###
# start celery:
# redis-server
# celery -A FWMsg.celery worker -l INFO
# celery -A FWMsg.celery beat -l INFO
###

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'FWMsg.settings')

app = Celery('FWMsg')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()
app.conf.timezone = 'Europe/Berlin'


def get_faellige_aufgaben():
    from FW.models import FreiwilligerAufgaben
    
    current_time = datetime.now()
    reminder_threshold = current_time - timedelta(days=14)
    
    return FreiwilligerAufgaben.objects.filter(
        erledigt=False,
        pending=False,
        faellig__lt=current_time
    ).filter(
        Q(last_reminder__lt=reminder_threshold) | Q(last_reminder__isnull=True)
    )



@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')


@app.task(name='send_email_aufgaben_daily')
def send_email_aufgaben_daily():
    from Global.send_email import send_mail_smtp

    faellige_aufgaben = get_faellige_aufgaben()
    start_time = datetime.now()

    response_json = {
        'count': len(faellige_aufgaben),
        'aufgaben_sent': [],
        'aufgaben_failed': [],
    }

    for aufgabe in faellige_aufgaben:
        if send_aufgaben_email(aufgabe):
            response_json['aufgaben_sent'].append({'id': aufgabe.id, 'name': aufgabe.aufgabe.name, 'freiwilliger': aufgabe.freiwilliger.first_name})
        else:
            response_json['aufgaben_failed'].append({'id': aufgabe.id, 'name': aufgabe.aufgabe.name, 'freiwilliger': aufgabe.freiwilliger.first_name})


    msg = f"""Uhrzeit: {datetime.now()}<br>
    Gebrauchte Zeit: {datetime.now() - start_time}<br><br>
    <br><br>Erfolgreich gesendet: {len(response_json['aufgaben_sent'])}<br>
    Fehlgeschlagen: {len(response_json['aufgaben_failed'])}<br><br>
    Gesamt: {len(response_json['aufgaben_sent']) + len(response_json['aufgaben_failed'])}<br><br>
    Fehlgeschlagene Aufgaben: {response_json['aufgaben_failed']}
    """

    send_mail_smtp(settings.SERVER_EMAIL, 'Aufgabenerinnerungen erfolgreich gesendet', msg, reply_to=settings.SERVER_EMAIL)

    return response_json


# cronjob, every day at 10:00 PM
app.conf.beat_schedule = {
    'send_email_aufgaben_daily': {
        'task': 'send_email_aufgaben_daily',
        'schedule': crontab(hour=23, minute=13),
    },
}
