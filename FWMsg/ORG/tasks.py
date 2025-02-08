from celery import shared_task
import base64

from Global.send_email import send_mail_smtp, format_register_email_org


@shared_task
def send_register_email_task(customuser_id):
    from Global.models import CustomUser
    customuser = CustomUser.objects.get(id=customuser_id)
    user = customuser.user
    org = customuser.org

    action_url = 'https://volunteer.solutions/first_login'
    org_name = org.name
    einmalpasswort = customuser.einmalpasswort
    freiwilliger_name = f"{user.first_name} {user.last_name}"
    username = user.username
    
    email_content = format_register_email_org(einmalpasswort, action_url, org_name, freiwilliger_name, username)
    subject = f'Account erstellt: {freiwilliger_name}'
    if send_mail_smtp(user.email, subject, email_content, reply_to=org.email):
        return True
    return False

@shared_task
def send_aufgabe_erledigt_email_task(aufgabe_id):
    from FW.models import FreiwilligerAufgaben
    try:
        aufgabe = FreiwilligerAufgaben.objects.get(id=aufgabe_id)
        subject = f'{aufgabe.freiwilliger.user.first_name} {aufgabe.freiwilliger.user.last_name} hat die Aufgabe {aufgabe.aufgabe.name} erledigt'
        org_email = aufgabe.freiwilliger.user.org.email
        email_content = f'{aufgabe.freiwilliger.user.first_name} {aufgabe.freiwilliger.user.last_name} hat die Aufgabe {aufgabe.aufgabe.name} erledigt. <br><br>Aufgabe braucht Bestätigung: {aufgabe.aufgabe.requires_submission}<br>Aufgabe hat Upload: {aufgabe.aufgabe.mitupload}'
        return send_mail_smtp(org_email, subject, email_content)
    except Exception as e:
        print(e)
        return False

@shared_task
def send_feedback_email_task(feedback_id):
    from Global.models import Feedback
    import json

    with open('FWMsg/.secrets.json', 'r') as f:
        secrets = json.load(f)

    feedback = Feedback.objects.get(id=feedback_id)
    subject = f'Feedback von {feedback.user.username}' if not feedback.anonymous else 'Anonymes Feedback'
    if send_mail_smtp(secrets['feedback_email'], subject, feedback.text):
        return True
    return False