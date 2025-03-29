import base64
from django.utils import timezone
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formatdate

from django.conf import settings

aufgaben_email_template = """
<html>
<body>
    <p>- English version below -</p>

    <br>

    <div style="display: flex; align-items: center; gap: 10px; justify-content: center; flex-wrap: wrap;">
        <img style="width: 50px;" src="data:image/png;base64,{base64_image}" alt="{org_name} Logo">
        <h2>{org_name}</h2>
    </div>

    <div>
        <p>Hallo {freiwilliger_name},</p>
        
        <p>dies ist eine automatische Erinnerung an die folgende Aufgabe:</p>
        
        <div>
            <strong>{aufgabe_name}</strong><br>
            Beschreibung: {aufgabe_beschreibung}<br>
            Fällig am: {aufgabe_deadline}
        </div>
        
        <p>Bitte schaue dir die Aufgabe an und bearbeite diese zeitnah.</p>
    </div>
    
    <div>
        Link zur Aufgabe: <a href="{action_url}">{action_url}</a>
    </div>
    
    <div>
        <p>Dies ist eine automatisch generierte E-Mail von Volunteer.Solutions - es wird keine Antwort erwartet.</p>
    </div>

    <br><br>

    <div>
        <strong>- English version -</strong>
    </div>

    <div>
        <p>Hello {freiwilliger_name},</p>
        
        <p>This is a reminder for the following task:</p>
        
        <div>
            <strong>{aufgabe_name}</strong><br>
            Description: {aufgabe_beschreibung}<br>
            Deadline: {aufgabe_deadline}
        </div>
        
        <p>Please check the task and complete it as soon as possible.</p>
    </div>
    
    <div>
        Check the task:
        <a href="{action_url}">{action_url}</a>
    </div>

    <div>
        <p>This is an automatically generated email from Volunteer.Solutions - no replies expected.</p>
    </div>
</body>
</html>
"""

new_aufgaben_email_template = """
<html>
<body>
    <p>- English version below -</p>

    <br>

    <div style="display: flex; align-items: center; gap: 10px; justify-content: center; flex-wrap: wrap;">
        <img style="width: 50px;" src="data:image/png;base64,{base64_image}" alt="{org_name} Logo">
        <h2>{org_name}</h2>
    </div>

    <div>
        <p>Hallo {freiwilliger_name},</p>
        <p>es gibt neue Aufgaben für Dich:</p>
        <div>
            <strong>{aufgaben_name}</strong><br>
        </div>
        <p>Bitte schaue dir die Aufgaben an und bearbeite diese zeitnah.</p>
        <div>
            <a href="{action_url}">{action_url}</a>
        </div>

        <p>Dies ist eine automatisch generierte E-Mail von Volunteer.Solutions - es wird keine Antwort erwartet.</p>

        <br><br>

        <div>
            <strong>- English version -</strong>
        </div>
        <div>
            <p>Hello {freiwilliger_name},</p>
            <p>there are new tasks for you:</p>
            <div>
                <strong>{aufgaben_name}</strong><br>
            </div>
        </div>
        <div>
            <p>This is an automatically generated email from Volunteer.Solutions - no replies expected.</p>
        </div>
    </div>
</body>
</html>
"""

register_email_fw_template = """
<html>
<body>
    <a>- English version below -</a>

    <div style="display: flex; align-items: center; gap: 10px; justify-content: center;">
        <img style="width: 50px;" src="data:image/png;base64,{base64_image}" alt="{org_name} Logo">
        <h2>{org_name}</h2>
    </div>

    <a>Hallo {freiwilliger_name},</a><br>
    <a>Es wurde ein Account für Dich bei <a href="{action_url}">Volunteer.Solutions</a> von der Organisation {org_name} erstellt.</a><br>
    <a>Volunteer.Solutions ist eine Plattform zur Organisation von Freiwilligenarbeit.</a><br>
    <br>
    <a>Bitte nutze für den Login die folgenden Daten:<br>Benutzername: {username}<br>Einmalpasswort: {einmalpasswort}</a>
    <p>Alternativ kannst Du dich auch über die folgende URL einloggen: <a href="{action_url}">{action_url}</a></p>
    <br>
    <small>Falls diese E-Mail in Ihrem Spam-Ordner gelandet ist, ist es empfehlenswert, diese E-Mail in den Posteingang zu verschieben und eine leere E-Mail an <a href="mailto:admin@volunteer.solutions">admin@volunteer.solutions</a> zu schreiben.</small>

    <br><br>

    <strong>- English version -</strong><br>
    <a>Hello {freiwilliger_name},</a><br>
    <a>An account has been created for you at <a href="{action_url}">Volunteer.Solutions</a> by the organisation {org_name}.</a><br>
    <a>Volunteer.Solutions is a platform for organising volunteer work.</a><br>
    <br>
    <a>Please use the following data for the login:<br>Username: {username}<br>One-time password: {einmalpasswort}</a>
    <p>Alternatively, you can log in via the following URL: <a href="{action_url}">{action_url}</a></p>
    <br>
    <small>If this email has landed in your spam folder, it is recommended to move this email to the inbox and send an empty email to <a href="mailto:admin@volunteer.solutions">admin@volunteer.solutions</a>.</small>
</body>
</html>
"""

register_email_org_template = """
<html>
<body>
    <p>An {org_name}</p>
    <p>Es wurde ein neuer Account auf Volunteer.Solutions erstellt.</p>
    <p>Bitte nutze für den Login die folgenden Daten:<br>Benutzername: {username}<br>Einmalpasswort: {einmalpasswort}</p>
    <p>Alternativ kannst Du dich auch über die folgende URL einloggen: <a href="{action_url}">{action_url}</a></p>
    <br>
    <small>Falls diese E-Mail in Ihrem Spam-Ordner gelandet ist, ist es empfehlenswert, diese E-Mail in den Posteingang zu verschieben und eine leere E-Mail an <a href="mailto:admin@volunteer.solutions">admin@volunteer.solutions</a> zu schreiben.</small>
</body>
</html>
"""

def format_aufgaben_email(aufgabe_name, aufgabe_deadline, base64_image, org_name, freiwilliger_name, action_url, aufgabe_beschreibung='',):
    return aufgaben_email_template.format(
        aufgabe_name=aufgabe_name,
        aufgabe_beschreibung=aufgabe_beschreibung,
        aufgabe_deadline=aufgabe_deadline.strftime('%d.%m.%Y') if aufgabe_deadline else '',
        base64_image=base64_image,
        org_name=org_name,
        freiwilliger_name=freiwilliger_name,
        action_url=action_url
    )

def format_new_aufgaben_email(aufgaben, base64_image, org_name, freiwilliger_name, action_url):
    aufgaben_name = ', '.join([aufgabe.aufgabe.name for aufgabe in aufgaben])
    return new_aufgaben_email_template.format(
        aufgaben_name=aufgaben_name,
        base64_image=base64_image,
        org_name=org_name,
        freiwilliger_name=freiwilliger_name,
        action_url=action_url
    )

def format_register_email_fw(einmalpasswort, action_url, base64_image, org_name, freiwilliger_name, username):
    return register_email_fw_template.format(
        einmalpasswort=einmalpasswort,
        action_url=action_url,
        base64_image=base64_image,
        org_name=org_name,
        freiwilliger_name=freiwilliger_name,
        username=username
    )

def format_register_email_org(einmalpasswort, action_url, org_name, freiwilliger_name, username):
    return register_email_org_template.format(
        einmalpasswort=einmalpasswort,
        action_url=action_url,
        org_name=org_name,
        freiwilliger_name=freiwilliger_name,
        username=username
    )

def get_logo_base64(org):
    with open(org.logo.path, "rb") as org_logo:
        base64_image = base64.b64encode(org_logo.read()).decode('utf-8')
    return base64_image

def send_aufgaben_email(aufgabe, org):
    # Get the organization logo URL
    action_url = 'https://volunteer.solutions/fw/aufgaben/' + str(aufgabe.aufgabe.id) + "/"
    
    base64_image = get_logo_base64(org)
    
    email_content = format_aufgaben_email(
        aufgabe_name=aufgabe.aufgabe.name,
        aufgabe_deadline=aufgabe.faellig,
        base64_image=base64_image,
        org_name=org.name,
        freiwilliger_name=f"{aufgabe.user.first_name} {aufgabe.user.last_name}",
        action_url=action_url,
        aufgabe_beschreibung=aufgabe.aufgabe.beschreibung if aufgabe.aufgabe.beschreibung else ''
    )   
    
    subject = f'Erinnerung: {aufgabe.aufgabe.name}'
    
    if send_mail_smtp(aufgabe.user.email, subject, email_content, reply_to=org.email):
        aufgabe.last_reminder = timezone.now()
        aufgabe.currently_sending = False
        aufgabe.save()
        return True
    
    aufgabe.currently_sending = False
    aufgabe.save()
    return False

def send_new_aufgaben_email(aufgaben, org):
    action_url = 'https://volunteer.solutions/fw/aufgaben/'

    base64_image = get_logo_base64(org)

    email_content = format_new_aufgaben_email(
        aufgaben=aufgaben,
        base64_image=base64_image,
        org_name=org.name,
        freiwilliger_name=f"{aufgaben[0].user.first_name} {aufgaben[0].user.last_name}",
        action_url=action_url
    )

    subject = f'Neue Aufgaben: {aufgaben[0].aufgabe.name}... und mehr'

    if send_mail_smtp(aufgaben[0].user.email, subject, email_content, reply_to=org.email):
        for aufgabe in aufgaben:
            aufgabe.last_reminder = timezone.now()
            aufgabe.currently_sending = False
            aufgabe.save()
            
        return True
    
    for aufgabe in aufgaben:
        aufgabe.currently_sending = False
        aufgabe.save()
    
    return False

def send_mail_smtp(receiver_email, subject, html_content, reply_to=None, cc=None):
    if not receiver_email or not subject or not html_content:
        return False

    smtp_server = settings.EMAIL_HOST
    port = settings.EMAIL_PORT
    sender_email = settings.EMAIL_HOST_USER
    password = settings.EMAIL_HOST_PASSWORD
    
    # Create a MIMEText email message
    message = MIMEMultipart("alternative")
    message["From"] = sender_email
    message["To"] = receiver_email
    message["Subject"] = subject
    message["Date"] = formatdate(localtime=True)

    if reply_to:
        message["Reply-To"] = reply_to

    if cc:
        message["Cc"] = cc

    # Add email content
    html_part = MIMEText(html_content, "html")
    message.attach(html_part)

    # Create a secure SSL context
    context = ssl.create_default_context()

    try:
        with smtplib.SMTP(smtp_server, port) as server:
            server.ehlo()  # Identify ourselves to the SMTP server
            server.starttls(context=context)  # Secure the connection
            server.ehlo()
            server.login(sender_email, password)  # Log in to the server
            server.sendmail(sender_email, receiver_email, message.as_string())  # Send the email
        print("Email sent successfully!")
        return True
    except smtplib.SMTPException as e:
        print(f"An error occurred: {e}")
        return False