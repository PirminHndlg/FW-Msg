import os

from django.conf import settings

from celery import Celery
from celery.schedules import crontab

from Global.send_email import send_aufgaben_email, send_new_aufgaben_email

from datetime import datetime, timedelta
from django.db.models import Q
from django.core.mail import mail_admins, send_mail

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


def get_faellige_aufgaben(before_date=False):
    from Global.models import UserAufgaben
    
    current_time = datetime.now()
    
    # Get all overdue tasks that haven't been completed or marked as pending
    overdue_tasks = UserAufgaben.objects.filter(
        erledigt=False,
        pending=False,
        last_reminder__isnull=False,
        faellig__lt=current_time
    )
    
    # For each task, check if enough days have passed since the last reminder
    tasks_to_remind = []
    for task in overdue_tasks:
        reminder_threshold = current_time.date() - timedelta(days=(task.aufgabe.repeat_push_days + 1))
        if task.last_reminder is None or task.last_reminder < reminder_threshold:
            tasks_to_remind.append(task)
            
    
    if before_date:        
        overdue_tasks_2 = UserAufgaben.objects.filter(
            erledigt=False,
            pending=False,
            last_reminder__isnull=False,
            faellig__gte=current_time
        )
        
        for task in overdue_tasks_2:
            if task.aufgabe.repeat_push_days:
                if (task.faellig - current_time.date()).days < task.aufgabe.repeat_push_days and (current_time.date() - task.last_reminder).days > task.aufgabe.repeat_push_days:
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

        faellige_aufgaben = get_faellige_aufgaben(before_date=True)
        start_time = datetime.now()
        for aufgabe in faellige_aufgaben:
            if send_aufgaben_email(aufgabe, aufgabe.aufgabe.org):
                response_json['aufgaben_sent'].append({'id': aufgabe.id, 'name': aufgabe.aufgabe.name, 'user': aufgabe.user.first_name})
            else:
                response_json['aufgaben_failed'].append({'id': aufgabe.id, 'name': aufgabe.aufgabe.name, 'user': aufgabe.user.first_name})
        
        response_json['count'] = len(faellige_aufgaben)

        # Format execution time
        execution_time = datetime.now().strftime('%d.%m.%Y %H:%M:%S')
        duration = datetime.now() - start_time
        duration_str = f"{duration.total_seconds():.2f} Sekunden"
        
        # Calculate totals
        total_reminders = len(response_json['aufgaben_sent']) + len(response_json['aufgaben_failed'])
        total_new_tasks = len(response_json['new_aufgaben_sent']) + len(response_json['new_aufgaben_failed'])
        
        # Format failed tasks for display
        failed_tasks_list = ""
        if response_json['aufgaben_failed']:
            failed_tasks_list = "<ul style='margin: 8px 0; padding-left: 20px;'>"
            for failed in response_json['aufgaben_failed']:
                failed_tasks_list += f"<li style='margin: 4px 0;'>{failed.get('name', 'Unbekannt')} (User: {failed.get('user', 'Unbekannt')}, ID: {failed.get('id', 'N/A')})</li>"
            failed_tasks_list += "</ul>"
        else:
            failed_tasks_list = "<p style='margin: 8px 0; color: #6c757d;'>Keine Fehler</p>"
        
        # Format new tasks sent
        new_tasks_sent_list = ""
        if response_json['new_aufgaben_sent']:
            new_tasks_sent_list = "<ul style='margin: 8px 0; padding-left: 20px;'>"
            for sent in response_json['new_aufgaben_sent']:
                aufgaben_names = ', '.join(sent.get('aufgaben', []))
                new_tasks_sent_list += f"<li style='margin: 4px 0;'>{sent.get('user', 'Unbekannt')}: {aufgaben_names}</li>"
            new_tasks_sent_list += "</ul>"
        else:
            new_tasks_sent_list = "<p style='margin: 8px 0; color: #6c757d;'>Keine neuen Aufgaben</p>"
        
        # Format new tasks failed
        new_tasks_failed_list = ""
        if response_json['new_aufgaben_failed']:
            new_tasks_failed_list = "<ul style='margin: 8px 0; padding-left: 20px;'>"
            for failed in response_json['new_aufgaben_failed']:
                aufgaben_names = ', '.join(failed.get('aufgaben', []))
                new_tasks_failed_list += f"<li style='margin: 4px 0;'>{failed.get('user', 'Unbekannt')}: {aufgaben_names}</li>"
            new_tasks_failed_list += "</ul>"
        else:
            new_tasks_failed_list = "<p style='margin: 8px 0; color: #6c757d;'>Keine Fehler</p>"
        
        # Create beautiful HTML email
        html_message = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                body {{
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
                    line-height: 1.6;
                    color: #333;
                    max-width: 600px;
                    margin: 0 auto;
                    padding: 20px;
                }}
                .header {{
                    border-bottom: 2px solid #0d6efd;
                    padding-bottom: 12px;
                    margin-bottom: 24px;
                }}
                .header h1 {{
                    margin: 0;
                    font-size: 20px;
                    font-weight: 600;
                    color: #0d6efd;
                }}
                .section {{
                    margin-bottom: 24px;
                }}
                .section-title {{
                    font-size: 14px;
                    font-weight: 600;
                    color: #495057;
                    margin-bottom: 8px;
                    text-transform: uppercase;
                    letter-spacing: 0.5px;
                }}
                .stat-box {{
                    background: #f8f9fa;
                    border-left: 3px solid #0d6efd;
                    padding: 12px 16px;
                    margin: 8px 0;
                    border-radius: 4px;
                }}
                .stat-success {{
                    border-left-color: #198754;
                }}
                .stat-error {{
                    border-left-color: #dc3545;
                }}
                .stat-label {{
                    font-size: 12px;
                    color: #6c757d;
                    margin-bottom: 4px;
                }}
                .stat-value {{
                    font-size: 18px;
                    font-weight: 600;
                    color: #212529;
                }}
                .info-row {{
                    display: flex;
                    justify-content: space-between;
                    padding: 8px 0;
                    border-bottom: 1px solid #e9ecef;
                }}
                .info-row:last-child {{
                    border-bottom: none;
                }}
                .info-label {{
                    color: #6c757d;
                    font-size: 13px;
                }}
                .info-value {{
                    color: #212529;
                    font-weight: 500;
                    font-size: 13px;
                }}
                ul {{
                    margin: 8px 0;
                    padding-left: 20px;
                }}
                li {{
                    margin: 4px 0;
                    font-size: 13px;
                }}
                .footer {{
                    margin-top: 32px;
                    padding-top: 16px;
                    border-top: 1px solid #e9ecef;
                    font-size: 12px;
                    color: #6c757d;
                    text-align: center;
                }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>✓ Aufgabenerinnerungen gesendet</h1>
            </div>
            
            <div class="section">
                <div class="section-title">Ausführung</div>
                <div class="info-row">
                    <span class="info-label">Uhrzeit:</span>
                    <span class="info-value">{execution_time}</span>
                </div>
                <div class="info-row">
                    <span class="info-label">Dauer:</span>
                    <span class="info-value">{duration_str}</span>
                </div>
            </div>
            
            <div class="section">
                <div class="section-title">Erinnerungen</div>
                <div class="stat-box stat-success">
                    <div class="stat-label">Erfolgreich gesendet</div>
                    <div class="stat-value">{len(response_json['aufgaben_sent'])}</div>
                </div>
                <div class="stat-box stat-error">
                    <div class="stat-label">Fehlgeschlagen</div>
                    <div class="stat-value">{len(response_json['aufgaben_failed'])}</div>
                </div>
                <div class="stat-box">
                    <div class="stat-label">Gesamt</div>
                    <div class="stat-value">{total_reminders}</div>
                </div>
            </div>
            
            <div class="section">
                <div class="section-title">Fehlgeschlagene Erinnerungen</div>
                {failed_tasks_list}
            </div>
            
            <div class="section">
                <div class="section-title">Neue Aufgaben</div>
                <div class="stat-box stat-success">
                    <div class="stat-label">Erfolgreich gesendet</div>
                    <div class="stat-value">{len(response_json['new_aufgaben_sent'])}</div>
                </div>
                <div class="stat-box stat-error">
                    <div class="stat-label">Fehlgeschlagen</div>
                    <div class="stat-value">{len(response_json['new_aufgaben_failed'])}</div>
                </div>
                <div class="stat-box">
                    <div class="stat-label">Gesamt</div>
                    <div class="stat-value">{total_new_tasks}</div>
                </div>
            </div>
            
            <div class="section">
                <div class="section-title">Erfolgreich gesendete neue Aufgaben</div>
                {new_tasks_sent_list}
            </div>
            
            <div class="section">
                <div class="section-title">Fehlgeschlagene neue Aufgaben</div>
                {new_tasks_failed_list}
            </div>
            
            <div class="footer">
                Automatische Benachrichtigung vom Aufgabenerinnerungs-System
            </div>
        </body>
        </html>
        """
        
        # Plain text version for email clients that don't support HTML
        plain_message = f"""Aufgabenerinnerungen erfolgreich gesendet

Ausführung:
Uhrzeit: {execution_time}
Dauer: {duration_str}

Erinnerungen:
Erfolgreich gesendet: {len(response_json['aufgaben_sent'])}
Fehlgeschlagen: {len(response_json['aufgaben_failed'])}
Gesamt: {total_reminders}

Fehlgeschlagene Erinnerungen:
{chr(10).join([f"- {f.get('name', 'Unbekannt')} (User: {f.get('user', 'Unbekannt')}, ID: {f.get('id', 'N/A')})" for f in response_json['aufgaben_failed']]) if response_json['aufgaben_failed'] else "Keine Fehler"}

Neue Aufgaben:
Erfolgreich gesendet: {len(response_json['new_aufgaben_sent'])}
Fehlgeschlagen: {len(response_json['new_aufgaben_failed'])}
Gesamt: {total_new_tasks}

Erfolgreich gesendete neue Aufgaben:
{chr(10).join([f"- {s.get('user', 'Unbekannt')}: {', '.join(s.get('aufgaben', []))}" for s in response_json['new_aufgaben_sent']]) if response_json['new_aufgaben_sent'] else "Keine neuen Aufgaben"}

Fehlgeschlagene neue Aufgaben:
{chr(10).join([f"- {f.get('user', 'Unbekannt')}: {', '.join(f.get('aufgaben', []))}" for f in response_json['new_aufgaben_failed']]) if response_json['new_aufgaben_failed'] else "Keine Fehler"}
        """

        mail_admins(
            subject='Aufgabenerinnerungen erfolgreich gesendet',
            message=plain_message,
            html_message=html_message
        )

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
                mail_admins(subject='Celery Task Failed', message=error_msg, html_message=error_msg)
            except:
                pass  # Don't let email failure prevent the task from failing
            raise
        
@app.task(name='send_birthday_reminder', bind=True, max_retries=3)
def send_birthday_reminder(self):
    try:
        from Global.models import CustomUser
        from Global.tasks import send_birthday_reminder_email_task
        # get all users with birthday tomorrow
        tomorrow = datetime.now().date() + timedelta(days=1)
        birthday_reminder_tomorrow = CustomUser.objects.filter(geburtsdatum__day=tomorrow.day, geburtsdatum__month=tomorrow.month)
        for user in birthday_reminder_tomorrow:
            send_birthday_reminder_email_task(user.id, is_tomorrow=True)
        
        today = datetime.now().date()
        birthday_reminder_today = CustomUser.objects.filter(geburtsdatum__day=today.day, geburtsdatum__month=today.month)
        for user in birthday_reminder_today:
            send_birthday_reminder_email_task(user.id, is_tomorrow=False)
    except Exception as exc:
        print(f"Error in send_birthday_reminder: {exc}")
        raise


# cronjob, every day at 10:00 AM
app.conf.beat_schedule = {
    'send_email_aufgaben_daily': {
        'task': 'send_email_aufgaben_daily',
        'schedule': crontab(hour=10, minute=0),
    },
    'send_birthday_reminder': {
        'task': 'send_birthday_reminder',
        'schedule': crontab(hour=10, minute=0),
    },
}
