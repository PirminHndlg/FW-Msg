import base64
from datetime import datetime, timedelta
from django.db.models import Q
from celery import shared_task

from FW.models import FreiwilligerAufgaben

from Global.send_email import send_mail_smtp, format_register_email


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

@shared_task
def send_register_email_task(freiwilliger_id):
    from FW.models import Freiwilliger
    freiwilliger = Freiwilliger.objects.get(id=freiwilliger_id)
    org = freiwilliger.user.org

    with open(org.logo.path, "rb") as org_logo:
        base64_image = base64.b64encode(org_logo.read()).decode('utf-8')
    action_url = 'https://volunteer.solutions'
    org_name = org.name
    einmalpasswort = '123456'
    freiwilliger_name = f"{freiwilliger.first_name} {freiwilliger.last_name}"
    username = freiwilliger.user.username
    
    email_content = format_register_email(einmalpasswort, action_url, base64_image, org_name, freiwilliger_name, username)
    subject = f'Account erstellt: {freiwilliger_name}'
    if send_mail_smtp(freiwilliger.email, subject, email_content, reply_to=org.email):
        return True
    return False
