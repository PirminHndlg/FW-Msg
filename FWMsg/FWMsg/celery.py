import os

from django.conf import settings

from celery import Celery
from celery.schedules import crontab

from Global.send_email import send_aufgaben_email


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
    from django.utils import timezone
    print("Getting faellige aufgaben")
    faellige_aufgaben = FreiwilligerAufgaben.objects.filter(faellig__lte=timezone.now().date())
    return faellige_aufgaben



@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')


@app.task(name='send_email_aufgaben_daily')
def send_email_aufgaben_daily():
    print("Sending email aufgaben daily")
    faellige_aufgaben = get_faellige_aufgaben()
    for aufgabe in faellige_aufgaben:
        send_aufgaben_email(aufgabe)

    return len(faellige_aufgaben)


# cronjob, every day at 10:00 PM
app.conf.beat_schedule = {
    # 'send_email_aufgaben_daily': {
    #     'task': 'send_email_aufgaben_daily',
    #     'schedule': crontab(hour=22, minute=21),
    # },
}
