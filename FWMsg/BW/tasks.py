from django.conf import settings
from Global.send_email import send_email_with_archive
from celery import shared_task
from BW.models import Bewerber
from django.core.mail import send_mail

application_complete_email_template = """
<body style="font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; margin: 0; padding: 0; color: #333333; line-height: 1.6; max-width: 500px; margin: 0 auto;">
    <div style="padding: 20px; background-color: #ffffff; border: 1px solid #eeeeee; border-radius: 5px;">
        <!-- Header -->
        <div style="text-align: center; padding-bottom: 15px; border-bottom: 1px solid #eeeeee; margin-bottom: 15px;">
            <h2 style="color: #3273dc; margin: 0; font-weight: 600;">{org_name}</h2>
        </div>
        
        <!-- Application Complete Info -->
        <div style="margin-bottom: 20px;">
            <h3 style="margin-top: 0; color: #4a4a4a;">{subject}</h3>
            
            <table style="width: 100%; border-collapse: collapse;">
                <tr>
                    <td style="padding: 8px 0; font-weight: bold; width: 140px;">Bewerber:in:</td>
                    <td style="padding: 8px 0;">{user_name}</td>
                </tr>
                <tr>
                    <td style="padding: 8px 0; font-weight: bold;">Eingegangen am:</td>
                    <td style="padding: 8px 0;">{changed_at}</td>
                </tr>
            </table>

            <!-- Action Button -->
            <div style="text-align: center; margin: 25px 0;">
                <a href="{action_url}" style="background-color: #3273dc; color: white; padding: 10px 20px; text-decoration: none; border-radius: 4px; font-weight: 500; display: inline-block;">Bewerbung ansehen</a>
            </div>
        </div>
        
        <!-- Footer -->
        <div style="border-top: 1px solid #eeeeee; padding-top: 15px; text-align: center; font-size: 12px; color: #888888;">
            Diese E-Mail wurde automatisch generiert.
            {unsubscribe_text}
        </div>
    </div>
</body>
"""

account_created_email_template = """
<body style="font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; margin: 0; padding: 0; color: #333333; line-height: 1.6; max-width: 500px; margin: 0 auto;">
    <div style="padding: 20px; background-color: #ffffff; border: 1px solid #eeeeee; border-radius: 5px;">
        <!-- Header -->
        <div style="text-align: center; padding-bottom: 15px; border-bottom: 1px solid #eeeeee; margin-bottom: 15px;">
            <h2 style="color: #3273dc; margin: 0; font-weight: 600;">{org_name}</h2>
        </div>
        
        <!-- Account Created Info -->
        <div style="margin-bottom: 20px;">
            <h3 style="margin-top: 0; color: #4a4a4a;">✨ Willkommen bei {org_name}</h3>
            
            <p style="margin: 20px 0;">Hallo {user_name},</p>
            
            <p style="margin: 20px 0;">vielen Dank für Ihre Registrierung. Um Ihren Account zu aktivieren, klicken Sie bitte auf den folgenden Button:</p>
            
            <!-- Verification Button -->
            <div style="text-align: center; margin: 25px 0;">
                <a href="{verification_url}" style="background-color: #3273dc; color: white; padding: 10px 20px; text-decoration: none; border-radius: 4px; font-weight: 500; display: inline-block;">Account verifizieren</a>
            </div>
            
            <p style="margin: 20px 0;">Falls der Button nicht funktioniert, können Sie auch diesen Link kopieren und in Ihren Browser einfügen:</p>
            <p style="margin: 10px 0; word-break: break-all; color: #666666; font-size: 14px;">{verification_url}</p>
            
            <div style="background-color: #f8f9fa; padding: 15px; border-radius: 4px; margin: 20px 0;">
                <p style="margin: 0 0 10px 0; font-weight: 500;">Ihre Zugangsdaten:</p>
                <p style="margin: 0;">Benutzername: <strong>{email}</strong></p>
                <p style="margin: 10px 0 0 0;">Nach der Verifizierung können Sie sich mit Ihrer E-Mail-Adresse als Benutzername einloggen.</p>
            </div>
            
            <p style="margin: 20px 0;">Nach der Verifizierung können Sie sich mit Ihren Zugangsdaten einloggen und Ihre Bewerbung fortsetzen.</p>
        </div>
        
        <!-- Footer -->
        <div style="border-top: 1px solid #eeeeee; padding-top: 15px; text-align: center; font-size: 12px; color: #888888;">
            Diese E-Mail wurde automatisch generiert.
            {unsubscribe_text}
        </div>
    </div>
</body>
"""


def format_application_complete_email(org_name, user_name, changed_at, action_url, unsubscribe_url=None, text_subject=None):
    unsubscribe_text = f'<p><a href="{unsubscribe_url}" style="color: #888888;">Abmelden</a></p>' if unsubscribe_url else ''
    
    return application_complete_email_template.format(
        org_name=org_name,
        user_name=user_name,
        changed_at=changed_at,
        action_url=action_url,
        unsubscribe_text=unsubscribe_text,
        subject=text_subject or 'Neue Bewerbung eingegangen'
    )

def format_account_created_email(org_name, user_name, verification_url, email, unsubscribe_url=None):
    unsubscribe_text = f'<p><a href="{unsubscribe_url}" style="color: #888888;">Abmelden</a></p>' if unsubscribe_url else ''
    
    return account_created_email_template.format(
        org_name=org_name,
        user_name=user_name,
        verification_url=verification_url,
        email=email,
        unsubscribe_text=unsubscribe_text
    )

@shared_task
def send_account_created_email(bewerber_id):
    from django.urls import reverse
    try:
        bewerber = Bewerber.objects.get(id=bewerber_id)
        user = bewerber.user
        
        # Create verification URL with the verification token
        verification_url = f"https://volunteer.solutions{reverse('verify_account', args=[bewerber.verification_token])}"
        
        # Format the email with our template
        email_content = format_account_created_email(
            org_name=bewerber.org.name,
            user_name=f"{user.first_name} {user.last_name}",
            verification_url=verification_url,
            email=user.email
        )
        
        subject = f'Neuer Account erstellt: {bewerber.org.name}'
        
        return send_email_with_archive(subject, email_content, settings.SERVER_EMAIL, [user.email], html_message=email_content)
    except Exception as e:
        print(f"Error sending account creation email: {e}")
        return False

@shared_task
def send_application_complete_email(bewerber_id):
    from django.urls import reverse
    try:
        bewerber = Bewerber.objects.get(id=bewerber_id)
        if bewerber.abgeschlossen:
            # Create action URL
            action_url = f"https://volunteer.solutions{reverse('application_detail', args=[bewerber.id])}"
            
            # Format the email with our template
            email_content = format_application_complete_email(
                org_name=bewerber.org.name,
                user_name=f"{bewerber.user.first_name} {bewerber.user.last_name}",
                changed_at=bewerber.abgeschlossen_am.strftime('%d.%m.%Y %H:%M'),
                action_url=action_url,
                
            )
            
            subject = f'Neue Bewerbung eingegangen: {bewerber.user.first_name} {bewerber.user.last_name}'
            org_email = bewerber.org.email
            send_email_with_archive(subject, email_content, settings.SERVER_EMAIL, [org_email], html_message=email_content)
            
            subject = f'Deine Bewerbung wurde eingereicht'
            action_url = f"https://volunteer.solutions{reverse('bw_home')}"
            email_content = format_application_complete_email(
                org_name=bewerber.org.name,
                user_name=f"{bewerber.user.first_name} {bewerber.user.last_name}",
                changed_at=bewerber.abgeschlossen_am.strftime('%d.%m.%Y %H:%M'),
                action_url=action_url,
                text_subject='Deine Bewerbung wurde eingereicht, wir werden uns schnellstmöglich um Ihre Bewerbung kümmern.'
            )
            send_email_with_archive(subject, email_content, settings.SERVER_EMAIL, [bewerber.user.email], html_message=email_content)
            
            return True
    except Exception as e:
        print(f"Error sending application complete email: {e}")
        return False
    