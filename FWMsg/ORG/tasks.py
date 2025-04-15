from celery import shared_task
import base64

from Global.send_email import send_mail_smtp, format_register_email_org, format_aufgabe_erledigt_email


@shared_task
def send_register_email_task(customuser_id):
    from Global.models import CustomUser
    customuser = CustomUser.objects.get(id=customuser_id)
    user = customuser.user
    org = customuser.org

    org_name = org.name
    einmalpasswort = customuser.einmalpasswort
    freiwilliger_name = f"{user.first_name} {user.last_name}"
    username = user.username
    action_url = f'https://volunteer.solutions/first_login?username={username}&einmalpasswort={einmalpasswort}'
    
    email_content = format_register_email_org(einmalpasswort, action_url, org_name, freiwilliger_name, username)
    subject = f'Account erstellt: {freiwilliger_name}'
    if send_mail_smtp(user.email, subject, email_content, reply_to=org.email):
        return True
    return False

@shared_task
def send_aufgabe_erledigt_email_task(aufgabe_id):
    from Global.models import UserAufgaben
    from django.urls import reverse
    
    try:
        aufgabe = UserAufgaben.objects.get(id=aufgabe_id)
        mail_to = ','.join(aufgabe.benachrichtigung_cc.split(',')) if aufgabe.benachrichtigung_cc else None
        
        # Create action URL
        action_url = f"https://volunteer.solutions{reverse('download_aufgabe', args=[aufgabe.id])}"
        
        # Check if there's a file uploaded
        has_file_upload = bool(aufgabe.file)
        
        # Format the email with our template
        email_content = format_aufgabe_erledigt_email(
            aufgabe_name=aufgabe.aufgabe.name,
            aufgabe_deadline=aufgabe.faellig,
            org_name=aufgabe.user.org.name,
            user_name=f"{aufgabe.user.first_name} {aufgabe.user.last_name}",
            action_url=action_url,
            requires_confirmation=aufgabe.aufgabe.requires_submission,
            has_file_upload=has_file_upload
        )
        
        subject = f'Aufgabe erledigt: {aufgabe.aufgabe.name} von {aufgabe.user.first_name} {aufgabe.user.last_name}'
        org_email = aufgabe.user.org.email
        
        return send_mail_smtp(org_email, subject, email_content, cc=mail_to)
    except Exception as e:
        print(f"Error sending task completion email: {e}")
        return False

@shared_task
def send_feedback_email_task(feedback_id):
    from Global.models import Feedback
    import json

    with open('FWMsg/.secrets.json', 'r') as f:
        secrets = json.load(f)

    feedback = Feedback.objects.get(id=feedback_id)
    subject = f'Feedback von {feedback.user.username}' if not feedback.anonymous else 'Anonymes Feedback'
    reply_to = feedback.user.email if not feedback.anonymous else None

    if send_mail_smtp(secrets['feedback_email'], subject, feedback.text, reply_to=reply_to):
        return True
    return False