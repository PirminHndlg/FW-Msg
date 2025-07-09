import os

from django.conf import settings

from celery import Celery
from celery.schedules import crontab

from Global.send_email import send_aufgaben_email, send_new_aufgaben_email

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

# Enhanced connection retry settings
app.conf.broker_connection_retry_on_startup = True
app.conf.broker_connection_retry = True
app.conf.broker_connection_max_retries = 10

# Redis-specific transport options
app.conf.broker_transport_options = {
    'max_retries': 100,
    'interval_start': 0,
    'interval_step': 2,
    'interval_max': 30,
    'socket_connect_timeout': 30,
    'socket_timeout': 30,
    'retry_on_timeout': True,
}

# Result backend settings
app.conf.result_backend_transport_options = {
    'max_retries': 100,
    'interval_start': 0,
    'interval_step': 2,
    'interval_max': 30,
    'socket_connect_timeout': 30,
    'socket_timeout': 30,
    'retry_on_timeout': True,
}

# Worker settings for better stability
app.conf.worker_prefetch_multiplier = 1
app.conf.worker_max_tasks_per_child = 1000
app.conf.worker_disable_rate_limits = False
app.conf.task_acks_late = True
app.conf.task_reject_on_worker_lost = True

# Handle connection loss gracefully
app.conf.worker_cancel_long_running_tasks_on_connection_loss = True

# Heartbeat settings for better connection monitoring
app.conf.broker_heartbeat = 30
app.conf.broker_heartbeat_checkrate = 2.0

# Additional Redis connection settings
app.conf.broker_pool_limit = 10
app.conf.broker_connection_timeout = 30
app.conf.broker_connection_retry = True
app.conf.broker_connection_max_retries = 10

# Redis connection pool settings
app.conf.broker_transport_options.update({
    'socket_keepalive': True,
})


def get_faellige_aufgaben():
    from Global.models import UserAufgaben
    
    current_time = datetime.now()
    
    # Get all overdue tasks that haven't been completed or marked as pending
    overdue_tasks = UserAufgaben.objects.filter(
        erledigt=False,
        pending=False,
        faellig__lt=current_time
    )
    
    # For each task, check if enough days have passed since the last reminder
    tasks_to_remind = []
    for task in overdue_tasks:
        reminder_threshold = current_time.date() - timedelta(days=task.aufgabe.repeat_push_days)
        if task.last_reminder is None or task.last_reminder < reminder_threshold:
            tasks_to_remind.append(task)
    
    return UserAufgaben.objects.filter(id__in=[task.id for task in tasks_to_remind])


def get_new_aufgaben():
    from Global.models import UserAufgaben
    
    return UserAufgaben.objects.filter(
        erledigt=False,
        pending=False,
        last_reminder__isnull=True
    )


@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')


@app.task(name='health_check')
def health_check():
    """Simple health check task to verify Celery and Redis connectivity."""
    return {
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'broker_connected': True
    }


@app.task(name='send_email_aufgaben_daily', bind=True, max_retries=3)
def send_email_aufgaben_daily(self):
    from Global.send_email import send_mail_smtp

    try:
        response_json = {
            'count': 0,
            'aufgaben_sent': [],
            'aufgaben_failed': [],
            'new_aufgaben_sent': [],
            'new_aufgaben_failed': [],
        }
        
        new_aufgaben = get_new_aufgaben()
        user_ids = new_aufgaben.values('user').distinct()
        for user_id in user_ids:
            aufgaben = new_aufgaben.filter(user_id=user_id['user'])
            if send_new_aufgaben_email(aufgaben, aufgaben[0].aufgabe.org):
                response_json['new_aufgaben_sent'].append({'aufgaben': [aufgabe.aufgabe.name for aufgabe in aufgaben], 'user': aufgaben[0].user.first_name})
            else:
                response_json['new_aufgaben_failed'].append({'aufgaben': [aufgabe.aufgabe.name for aufgabe in aufgaben], 'user': aufgaben[0].user.first_name})

        faellige_aufgaben = get_faellige_aufgaben()
        start_time = datetime.now()
        for aufgabe in faellige_aufgaben:
            if send_aufgaben_email(aufgabe, aufgabe.aufgabe.org):
                response_json['aufgaben_sent'].append({'id': aufgabe.id, 'name': aufgabe.aufgabe.name, 'user': aufgabe.user.first_name})
            else:
                response_json['aufgaben_failed'].append({'id': aufgabe.id, 'name': aufgabe.aufgabe.name, 'user': aufgabe.user.first_name})
        
        response_json['count'] = len(faellige_aufgaben)

        msg = f"""Uhrzeit: {datetime.now()}<br>
        Gebrauchte Zeit: {datetime.now() - start_time}<br><br>
        <br><br>Erfolgreich gesendet: {len(response_json['aufgaben_sent'])}<br>
        Fehlgeschlagen: {len(response_json['aufgaben_failed'])}<br><br>
        Gesamt: {len(response_json['aufgaben_sent']) + len(response_json['aufgaben_failed'])}<br><br>
        Fehlgeschlagene Aufgaben: {response_json['aufgaben_failed']}<br><br>
        Erfolgreich gesendete neue Aufgaben: {response_json['new_aufgaben_sent']}<br><br>
        Fehlgeschlagene neue Aufgaben: {response_json['new_aufgaben_failed']}<br><br>
        Gesamt: {len(response_json['new_aufgaben_sent']) + len(response_json['new_aufgaben_failed'])}
        """

        send_mail_smtp(settings.SERVER_EMAIL, 'Aufgabenerinnerungen erfolgreich gesendet', msg, reply_to=settings.SERVER_EMAIL)

        return response_json
        
    except Exception as exc:
        # Log the error and retry if we haven't exceeded max retries
        print(f"Error in send_email_aufgaben_daily: {exc}")
        if self.request.retries < self.max_retries:
            raise self.retry(countdown=60 * (2 ** self.request.retries), exc=exc)
        else:
            # If we've exhausted retries, send a notification about the failure
            error_msg = f"Task send_email_aufgaben_daily failed after {self.max_retries} retries. Error: {exc}"
            try:
                send_mail_smtp(settings.SERVER_EMAIL, 'Celery Task Failed', error_msg, reply_to=settings.SERVER_EMAIL)
            except:
                pass  # Don't let email failure prevent the task from failing
            raise


# cronjob, every day at 10:00 PM
app.conf.beat_schedule = {
    'send_email_aufgaben_daily': {
        'task': 'send_email_aufgaben_daily',
        'schedule': crontab(hour=16, minute=30),
    },
}
