import base64
from django.utils import timezone
from django.core.mail import send_mail

from django.conf import settings

from .push_notification import send_push_notification_to_user

aufgaben_email_template = """
<body style="font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; margin: 0; padding: 0; color: #333333; line-height: 1.6; max-width: 600px; margin: 0 auto;">
    <div style="padding: 20px; background-color: #ffffff;">
        <!-- Organization Header -->
        <div style="text-align: center; padding-bottom: 20px; border-bottom: 1px solid #eeeeee; margin-bottom: 20px;">
            <img style="width: 60px; height: auto; margin-bottom: 10px;" src="data:image/png;base64,{base64_image}" alt="{org_name} Logo">
            <h2 style="color: #3273dc; margin: 0; font-weight: 600;">{org_name}</h2>
        </div>
        
        <!-- German Version -->
        <div style="margin-bottom: 30px;">
            <p style="font-size: 16px; margin-bottom: 15px;">Hallo {user_name},</p>
            
            <p>Dies ist eine automatische Erinnerung an die folgende Aufgabe:</p>
            
            <div style="background-color: #f7f9fc; border-left: 4px solid #3273dc; padding: 15px; margin: 15px 0; border-radius: 3px;">
                <p style="font-weight: 600; margin: 0 0 10px 0; font-size: 17px; color: #3273dc;">{aufgabe_name}</p>
                <p style="margin: 5px 0;"><span style="color: #666666;">Beschreibung:</span> {aufgabe_beschreibung}</p>
                <p style="margin: 5px 0;"><span style="color: #666666;">Fällig am:</span> <span style="font-weight: 500;">{aufgabe_deadline}</span></p>
            </div>
            
            <p>Bitte schaue dir die Aufgabe an und bearbeite diese zeitnah.</p>
            
            <div style="text-align: center; margin: 25px 0;">
                <a href="{action_url}" style="background-color: #3273dc; color: white; padding: 10px 20px; text-decoration: none; border-radius: 4px; font-weight: 500; display: inline-block;">Zur Aufgabe</a>
            </div>
        </div>
        
        <!-- Divider -->
        <div style="border-top: 1px solid #eeeeee; margin: 20px 0;"></div>
        
        <!-- English Version -->
        <div style="margin-bottom: 25px;">
            <p style="font-size: 15px; color: #444444; margin-bottom: 15px;"><strong>English version</strong></p>
            
            <p>Hello {user_name},</p>
            
            <p>This is a reminder for the following task:</p>
            
            <div style="background-color: #f7f9fc; border-left: 4px solid #3273dc; padding: 15px; margin: 15px 0; border-radius: 3px;">
                <p style="font-weight: 600; margin: 0 0 10px 0; font-size: 17px; color: #3273dc;">{aufgabe_name}</p>
                <p style="margin: 5px 0;"><span style="color: #666666;">Description:</span> {aufgabe_beschreibung}</p>
                <p style="margin: 5px 0;"><span style="color: #666666;">Deadline:</span> <span style="font-weight: 500;">{aufgabe_deadline}</span></p>
            </div>
            
            <p>Please check the task and complete it as soon as possible.</p>
            
            <div style="text-align: center; margin: 25px 0;">
                <a href="{action_url}" style="background-color: #3273dc; color: white; padding: 10px 20px; text-decoration: none; border-radius: 4px; font-weight: 500; display: inline-block;">View Task</a>
            </div>
        </div>
        
        <!-- Footer -->
        <div style="text-align: center; font-size: 13px; color: #666666; margin-top: 30px; padding-top: 20px; border-top: 1px solid #eeeeee;">
            <p style="margin: 5px 0;">Dies ist eine automatisch generierte E-Mail von Volunteer.Solutions</p>
            <p style="margin: 5px 0;">Um keine weiteren E-Mails zu erhalten, <a href="{unsubscribe_url}" style="color: #3273dc; text-decoration: none;">klicke hier</a></p>
            <p style="margin: 5px 0; color: #999999;">This is an automatically generated email - no reply expected</p>
        </div>
    </div>
</body>
"""

new_aufgaben_email_template = """
<body style="font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; margin: 0; padding: 0; color: #333333; line-height: 1.6; max-width: 600px; margin: 0 auto;">
    <div style="padding: 20px; background-color: #ffffff;">
        <!-- Organization Header -->
        <div style="text-align: center; padding-bottom: 20px; border-bottom: 1px solid #eeeeee; margin-bottom: 20px;">
            <img style="width: 60px; height: auto; margin-bottom: 10px;" src="data:image/png;base64,{base64_image}" alt="{org_name} Logo">
            <h2 style="color: #3273dc; margin: 0; font-weight: 600;">{org_name}</h2>
        </div>
        
        <!-- German Version -->
        <div style="margin-bottom: 30px;">
            <p style="font-size: 16px; margin-bottom: 15px;">Hallo {user_name},</p>
            
            <p>Es gibt neue Aufgaben für Dich:</p>
            
            <div style="background-color: #f7f9fc; border-left: 4px solid #3273dc; padding: 15px; margin: 15px 0; border-radius: 3px;">
                <p style="font-weight: 600; margin: 0; font-size: 17px; color: #3273dc;">{aufgaben_name}</p>
            </div>
            
            <p>Bitte schaue dir die Aufgaben an und bearbeite diese zeitnah.</p>
            
            <div style="text-align: center; margin: 25px 0;">
                <a href="{action_url}" style="background-color: #3273dc; color: white; padding: 10px 20px; text-decoration: none; border-radius: 4px; font-weight: 500; display: inline-block;">Zu den Aufgaben</a>
            </div>
        </div>
        
        <!-- Divider -->
        <div style="border-top: 1px solid #eeeeee; margin: 20px 0;"></div>
        
        <!-- English Version -->
        <div style="margin-bottom: 25px;">
            <p style="font-size: 15px; color: #444444; margin-bottom: 15px;"><strong>English version</strong></p>
            
            <p>Hello {user_name},</p>
            
            <p>There are new tasks for you:</p>
            
            <div style="background-color: #f7f9fc; border-left: 4px solid #3273dc; padding: 15px; margin: 15px 0; border-radius: 3px;">
                <p style="font-weight: 600; margin: 0; font-size: 17px; color: #3273dc;">{aufgaben_name}</p>
            </div>
            
            <p>Please check the tasks and complete them as soon as possible.</p>
            
            <div style="text-align: center; margin: 25px 0;">
                <a href="{action_url}" style="background-color: #3273dc; color: white; padding: 10px 20px; text-decoration: none; border-radius: 4px; font-weight: 500; display: inline-block;">View Tasks</a>
            </div>
        </div>
        
        <!-- Footer -->
        <div style="text-align: center; font-size: 13px; color: #666666; margin-top: 30px; padding-top: 20px; border-top: 1px solid #eeeeee;">
            <p style="margin: 5px 0;">Dies ist eine automatisch generierte E-Mail von Volunteer.Solutions</p>
            <p style="margin: 5px 0;">Um keine weiteren E-Mails zu erhalten, <a href="{unsubscribe_url}" style="color: #3273dc; text-decoration: none;">klicke hier</a></p>
            <p style="margin: 5px 0; color: #999999;">This is an automatically generated email - no reply expected</p>
        </div>
    </div>
</body>
"""

aufgabe_erledigt_email_template = """
<body style="font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; margin: 0; padding: 0; color: #333333; line-height: 1.6; max-width: 500px; margin: 0 auto;">
    <div style="padding: 20px; background-color: #ffffff; border: 1px solid #eeeeee; border-radius: 5px;">
        <!-- Header -->
        <div style="text-align: center; padding-bottom: 15px; border-bottom: 1px solid #eeeeee; margin-bottom: 15px;">
            <h2 style="color: #3273dc; margin: 0; font-weight: 600;">{org_name}</h2>
        </div>
        
        <!-- Task Completion Info -->
        <div style="margin-bottom: 20px;">
            <h3 style="margin-top: 0; color: #4a4a4a;">✅ Aufgabe erledigt</h3>
            
            <table style="width: 100%; border-collapse: collapse;">
                <tr>
                    <td style="padding: 8px 0; font-weight: bold; width: 140px;">Aufgabe:</td>
                    <td style="padding: 8px 0;">{aufgabe_name}</td>
                </tr>
                <tr>
                    <td style="padding: 8px 0; font-weight: bold;">Erledigt von:</td>
                    <td style="padding: 8px 0;">{user_name}</td>
                </tr>
                <tr>
                    <td style="padding: 8px 0; font-weight: bold;">Fällig am:</td>
                    <td style="padding: 8px 0;">{aufgabe_deadline}</td>
                </tr>
                <tr>
                    <td style="padding: 8px 0; font-weight: bold;">Bestätigung nötig:</td>
                    <td style="padding: 8px 0;">{requires_confirmation}</td>
                </tr>
                <tr>
                    <td style="padding: 8px 0; font-weight: bold;">Datei hochgeladen:</td>
                    <td style="padding: 8px 0;">{has_file_upload}</td>
                </tr>
            </table>

            <!-- Action Button -->
            {action_button}
        </div>
        
        <!-- Footer -->
        <div style="border-top: 1px solid #eeeeee; padding-top: 15px; text-align: center; font-size: 12px; color: #888888;">
            Diese E-Mail wurde automatisch generiert.
            {unsubscribe_text}
        </div>
    </div>
</body>
"""

register_email_fw_template = """
<body style="font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; margin: 0; padding: 0; color: #333333; line-height: 1.6; max-width: 600px; margin: 0 auto;">
    <div style="padding: 20px; background-color: #ffffff;">
        <!-- Organization Header -->
        <div style="text-align: center; padding-bottom: 20px; border-bottom: 1px solid #eeeeee; margin-bottom: 20px;">
            <img style="width: 60px; height: auto; margin-bottom: 10px;" src="data:image/png;base64,{base64_image}" alt="{org_name} Logo">
            <h2 style="color: #3273dc; margin: 0; font-weight: 600;">{org_name}</h2>
        </div>
        
        <!-- German Version -->
        <div style="margin-bottom: 30px;">
            <p style="font-size: 16px; margin-bottom: 15px;">Hallo {user_name},</p>
            
            <p>Es wurde ein Account für Dich bei Volunteer.Solutions von der Organisation {org_name} erstellt.</p>
            <p>Volunteer.Solutions ist eine Plattform zur Organisation von Freiwilligenarbeit.</p>
            
            <div style="background-color: #f7f9fc; border-radius: 4px; padding: 20px; margin: 20px 0;">
                <p style="margin: 0 0 10px 0; font-weight: 500;">Bitte nutze für den Login die folgenden Daten:</p>
                <p style="margin: 5px 0;"><span style="display: inline-block; width: 120px; color: #666666;">Benutzername:</span> <span style="font-weight: 500;">{username}</span></p>
                <p style="margin: 5px 0;"><span style="display: inline-block; width: 120px; color: #666666;">Einmalpasswort:</span> <span style="font-weight: 500; font-family: monospace; font-size: 16px; letter-spacing: 1px;">{einmalpasswort}</span></p>
            </div>
            
            <div style="text-align: center; margin: 25px 0;">
                <a href="{action_url}" style="background-color: #3273dc; color: white; padding: 10px 20px; text-decoration: none; border-radius: 4px; font-weight: 500; display: inline-block;">Jetzt einloggen</a>
            </div>
        </div>
        
        <!-- Divider -->
        <div style="border-top: 1px solid #eeeeee; margin: 20px 0;"></div>
        
        <!-- English Version -->
        <div style="margin-bottom: 25px;">
            <p style="font-size: 15px; color: #444444; margin-bottom: 15px;"><strong>English version</strong></p>
            
            <p>Hello {user_name},</p>
            
            <p>An account has been created for you at Volunteer.Solutions by the organization {org_name}.</p>
            <p>Volunteer.Solutions is a platform for organizing volunteer work.</p>
            
            <div style="background-color: #f7f9fc; border-radius: 4px; padding: 20px; margin: 20px 0;">
                <p style="margin: 0 0 10px 0; font-weight: 500;">Please use the following data for login:</p>
                <p style="margin: 5px 0;"><span style="display: inline-block; width: 120px; color: #666666;">Username:</span> <span style="font-weight: 500;">{username}</span></p>
                <p style="margin: 5px 0;"><span style="display: inline-block; width: 120px; color: #666666;">One-time password:</span> <span style="font-weight: 500; font-family: monospace; font-size: 16px; letter-spacing: 1px;">{einmalpasswort}</span></p>
            </div>
            
            <div style="text-align: center; margin: 25px 0;">
                <a href="{action_url}" style="background-color: #3273dc; color: white; padding: 10px 20px; text-decoration: none; border-radius: 4px; font-weight: 500; display: inline-block;">Login now</a>
            </div>
        </div>
        
        <!-- Spam Note -->
        <div style="font-size: 12px; color: #777777; margin-top: 20px; padding: 15px; background-color: #f9f9f9; border-radius: 4px;">
            <p style="margin: 0;">Falls diese E-Mail in Ihrem Spam-Ordner gelandet ist, ist es empfehlenswert, diese E-Mail in den Posteingang zu verschieben und eine leere E-Mail an <a href="mailto:admin@volunteer.solutions" style="color: #3273dc; text-decoration: none;">admin@volunteer.solutions</a> zu schreiben.</p>
            <p style="margin: 5px 0 0 0;">If this email has landed in your spam folder, it is recommended to move it to your inbox and send an empty email to <a href="mailto:admin@volunteer.solutions" style="color: #3273dc; text-decoration: none;">admin@volunteer.solutions</a>.</p>
        </div>
    </div>
</body>
"""

register_email_org_template = """
<body style="font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; margin: 0; padding: 0; color: #333333; line-height: 1.6; max-width: 600px; margin: 0 auto;">
    <div style="padding: 20px; background-color: #ffffff;">
        <!-- Header -->
        <div style="text-align: center; padding-bottom: 20px; border-bottom: 1px solid #eeeeee; margin-bottom: 20px;">
            <h2 style="color: #3273dc; margin: 0; font-weight: 600;">Volunteer.Solutions</h2>
            <p style="margin: 10px 0 0 0; color: #666666;">Plattform für {org_name}</p>
        </div>
        
        <!-- Content -->
        <div style="margin-bottom: 30px;">
            <p style="font-size: 16px; margin-bottom: 15px;">An {org_name},</p>
            
            <p>Es wurde ein neuer Account auf Volunteer.Solutions erstellt.</p>
            
            <div style="background-color: #f7f9fc; border-radius: 4px; padding: 20px; margin: 20px 0;">
                <p style="margin: 0 0 10px 0; font-weight: 500;">Bitte nutze für den Login die folgenden Daten:</p>
                <p style="margin: 5px 0;"><span style="display: inline-block; width: 120px; color: #666666;">Benutzername:</span> <span style="font-weight: 500;">{username}</span></p>
                <p style="margin: 5px 0;"><span style="display: inline-block; width: 120px; color: #666666;">Einmalpasswort:</span> <span style="font-weight: 500; font-family: monospace; font-size: 16px; letter-spacing: 1px;">{einmalpasswort}</span></p>
            </div>
            
            <div style="text-align: center; margin: 25px 0;">
                <a href="{action_url}" style="background-color: #3273dc; color: white; padding: 10px 20px; text-decoration: none; border-radius: 4px; font-weight: 500; display: inline-block;">Jetzt einloggen</a>
            </div>
        </div>
        
        <!-- Spam Note -->
        <div style="font-size: 12px; color: #777777; margin-top: 20px; padding: 15px; background-color: #f9f9f9; border-radius: 4px;">
            <p style="margin: 0;">Falls diese E-Mail in Ihrem Spam-Ordner gelandet ist, ist es empfehlenswert, diese E-Mail in den Posteingang zu verschieben und eine leere E-Mail an <a href="mailto:admin@volunteer.solutions" style="color: #3273dc; text-decoration: none;">admin@volunteer.solutions</a> zu schreiben.</p>
        </div>
    </div>
</body>
"""

mail_calendar_reminder_email_template = """
<body style="font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; margin: 0; padding: 0; color: #333333; line-height: 1.6; max-width: 600px; margin: 0 auto;">
    <div style="padding: 20px; background-color: #ffffff;">
        <!-- Organization Header -->
        <div style="text-align: center; padding-bottom: 20px; border-bottom: 1px solid #eeeeee; margin-bottom: 20px;">
            <img style="width: 60px; height: auto; margin-bottom: 10px;" src="data:image/png;base64,{base64_image}" alt="{org_name} Logo">
            <h2 style="color: #3273dc; margin: 0; font-weight: 600;">{org_name}</h2>
        </div>
        
        <!-- German Version -->
        <div style="margin-bottom: 30px;">
            <p style="font-size: 16px; margin-bottom: 15px;">Hallo {user_name},</p>
            
            <p>Es gibt einen neuen Kalendereintrag für Dich:</p>
            
            <div style="background-color: #f7f9fc; border-left: 4px solid #3273dc; padding: 15px; margin: 15px 0; border-radius: 3px;">
                <p style="font-weight: 600; margin: 0 0 10px 0; font-size: 17px; color: #3273dc;">{event_name}</p>
                <p style="margin: 5px 0;"><span style="color: #666666;">Start:</span> <span style="font-weight: 500;">{event_start}</span></p>
                <p style="margin: 5px 0;"><span style="color: #666666;">Ende:</span> <span style="font-weight: 500;">{event_end}</span></p>
                {event_description_html}
            </div>
            
            <div style="text-align: center; margin: 25px 0;">
                <a href="{action_url}" style="background-color: #3273dc; color: white; padding: 10px 20px; text-decoration: none; border-radius: 4px; font-weight: 500; display: inline-block;">Zum Kalender</a>
            </div>
        </div>
        
        <!-- Divider -->
        <div style="border-top: 1px solid #eeeeee; margin: 20px 0;"></div>
        
        <!-- English Version -->
        <div style="margin-bottom: 25px;">
            <p style="font-size: 15px; color: #444444; margin-bottom: 15px;"><strong>English version</strong></p>
            
            <p>Hello {user_name},</p>
            
            <p>There is a new calendar entry for you:</p>
            
            <div style="background-color: #f7f9fc; border-left: 4px solid #3273dc; padding: 15px; margin: 15px 0; border-radius: 3px;">
                <p style="font-weight: 600; margin: 0 0 10px 0; font-size: 17px; color: #3273dc;">{event_name}</p>
                <p style="margin: 5px 0;"><span style="color: #666666;">Start:</span> <span style="font-weight: 500;">{event_start}</span></p>
                <p style="margin: 5px 0;"><span style="color: #666666;">End:</span> <span style="font-weight: 500;">{event_end}</span></p>
                {event_description_html}
            </div>
            
            <div style="text-align: center; margin: 25px 0;">
                <a href="{action_url}" style="background-color: #3273dc; color: white; padding: 10px 20px; text-decoration: none; border-radius: 4px; font-weight: 500; display: inline-block;">View Calendar</a>
            </div>
        </div>
        
        <!-- Footer -->
        <div style="text-align: center; font-size: 13px; color: #666666; margin-top: 30px; padding-top: 20px; border-top: 1px solid #eeeeee;">
            <p style="margin: 5px 0;">Dies ist eine automatisch generierte E-Mail von Volunteer.Solutions</p>
            <p style="margin: 5px 0;">Um keine weiteren E-Mails zu erhalten, <a href="{unsubscribe_url}" style="color: #3273dc; text-decoration: none;">klicke hier</a></p>
            <p style="margin: 5px 0; color: #999999;">This is an automatically generated email - no reply expected</p>
        </div>
    </div>
</body>
"""

new_post_email_template = """
<body style="font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; margin: 0; padding: 0; color: #333333; line-height: 1.6; max-width: 600px; margin: 0 auto;">
    <div style="padding: 20px; background-color: #ffffff;">
        <!-- Organization Header -->
        <div style="text-align: center; padding-bottom: 20px; border-bottom: 1px solid #eeeeee; margin-bottom: 20px;">
            <img style="width: 60px; height: auto; margin-bottom: 10px;" src="data:image/png;base64,{base64_image}" alt="{org_name} Logo">
            <h2 style="color: #3273dc; margin: 0; font-weight: 600;">{org_name}</h2>
        </div>
        
        <!-- German Version -->
        <div style="margin-bottom: 30px;">
            <p style="font-size: 16px; margin-bottom: 15px;">Hallo {user_name},</p>
            
            <p>Es gibt einen neuen Post von {author_name}:</p>
            
            <div style="background-color: #f7f9fc; border-left: 4px solid #3273dc; padding: 15px; margin: 15px 0; border-radius: 3px;">
                <p style="font-weight: 600; margin: 0 0 10px 0; font-size: 17px; color: #3273dc;">{post_title}</p>
                <p style="margin: 5px 0;"><span style="color: #666666;">Von:</span> <span style="font-weight: 500;">{author_name}</span></p>
                <p style="margin: 5px 0;"><span style="color: #666666;">Erstellt am:</span> <span style="font-weight: 500;">{post_date}</span></p>
                {survey_info_html}
                <div style="margin-top: 10px; padding: 10px; background-color: #ffffff; border-radius: 4px; border: 1px solid #e9ecef;">
                    <p style="margin: 0; color: #555555; font-size: 14px;">{post_text}</p>
                </div>
            </div>
            
            <div style="text-align: center; margin: 25px 0;">
                <a href="{action_url}" style="background-color: #3273dc; color: white; padding: 10px 20px; text-decoration: none; border-radius: 4px; font-weight: 500; display: inline-block;">Post ansehen</a>
            </div>
        </div>
        
        <!-- Divider -->
        <div style="border-top: 1px solid #eeeeee; margin: 20px 0;"></div>
        
        <!-- English Version -->
        <div style="margin-bottom: 25px;">
            <p style="font-size: 15px; color: #444444; margin-bottom: 15px;"><strong>English version</strong></p>
            
            <p>Hello {user_name},</p>
            
            <p>There is a new post from {author_name}:</p>
            
            <div style="background-color: #f7f9fc; border-left: 4px solid #3273dc; padding: 15px; margin: 15px 0; border-radius: 3px;">
                <p style="font-weight: 600; margin: 0 0 10px 0; font-size: 17px; color: #3273dc;">{post_title}</p>
                <p style="margin: 5px 0;"><span style="color: #666666;">From:</span> <span style="font-weight: 500;">{author_name}</span></p>
                <p style="margin: 5px 0;"><span style="color: #666666;">Created on:</span> <span style="font-weight: 500;">{post_date}</span></p>
                {survey_info_html}
                <div style="margin-top: 10px; padding: 10px; background-color: #ffffff; border-radius: 4px; border: 1px solid #e9ecef;">
                    <p style="margin: 0; color: #555555; font-size: 14px;">{post_text}</p>
                </div>
            </div>
            
            <div style="text-align: center; margin: 25px 0;">
                <a href="{action_url}" style="background-color: #3273dc; color: white; padding: 10px 20px; text-decoration: none; border-radius: 4px; font-weight: 500; display: inline-block;">View Post</a>
            </div>
        </div>
        
        <!-- Footer -->
        <div style="text-align: center; font-size: 13px; color: #666666; margin-top: 30px; padding-top: 20px; border-top: 1px solid #eeeeee;">
            <p style="margin: 5px 0;">Dies ist eine automatisch generierte E-Mail von Volunteer.Solutions</p>
            <p style="margin: 5px 0;">Um keine weiteren E-Mails zu erhalten, <a href="{unsubscribe_url}" style="color: #3273dc; text-decoration: none;">klicke hier</a></p>
            <p style="margin: 5px 0; color: #999999;">This is an automatically generated email - no reply expected</p>
        </div>
    </div>
</body>
"""

def format_aufgaben_email(aufgabe_name, aufgabe_deadline, base64_image, org_name, user_name, action_url, aufgabe_beschreibung='', unsubscribe_url=None):
    return aufgaben_email_template.format(
        aufgabe_name=aufgabe_name,
        aufgabe_beschreibung=aufgabe_beschreibung,
        aufgabe_deadline=aufgabe_deadline.strftime('%d.%m.%Y') if aufgabe_deadline else '',
        base64_image=base64_image,
        org_name=org_name,
        user_name=user_name,
        action_url=action_url,
        unsubscribe_url=unsubscribe_url
    )

def format_new_aufgaben_email(aufgaben, base64_image, org_name, user_name, action_url, unsubscribe_url=None):
    aufgaben_name = ', '.join([aufgabe.aufgabe.name for aufgabe in aufgaben])
    return new_aufgaben_email_template.format(
        aufgaben_name=aufgaben_name,
        base64_image=base64_image,
        org_name=org_name,
        user_name=user_name,
        action_url=action_url,
        unsubscribe_url=unsubscribe_url
    )

def format_aufgabe_erledigt_email(aufgabe_name, aufgabe_deadline, org_name, user_name, action_url, requires_confirmation=False, has_file_upload=False, aufgabe_beschreibung='', unsubscribe_url=None):
    unsubscribe_text = f'<p><a href="{unsubscribe_url}" style="color: #888888;">Abmelden</a></p>' if unsubscribe_url else ''
    
    # Convert boolean values to Yes/No text in German
    requires_confirmation_text = "Ja" if requires_confirmation else "Nein"
    has_file_upload_text = "Ja" if has_file_upload else "Nein"

    if has_file_upload:
        action_button = f'<div style="text-align: center; margin: 25px 0;"><a href="{action_url}" style="background-color: #3273dc; color: white; padding: 10px 20px; text-decoration: none; border-radius: 4px; font-weight: 500; display: inline-block;">Datei herunterladen</a></div>'
    else:
        action_button = ''
    
    return aufgabe_erledigt_email_template.format(
        aufgabe_name=aufgabe_name,
        aufgabe_beschreibung=aufgabe_beschreibung,
        aufgabe_deadline=aufgabe_deadline.strftime('%d.%m.%Y') if aufgabe_deadline else '',
        org_name=org_name,
        user_name=user_name,
        requires_confirmation=requires_confirmation_text,
        has_file_upload=has_file_upload_text,
        unsubscribe_text=unsubscribe_text,
        action_button=action_button
    )

def format_register_email_fw(einmalpasswort, action_url, base64_image, org_name, user_name, username):
    return register_email_fw_template.format(
        einmalpasswort=einmalpasswort,
        action_url=action_url,
        base64_image=base64_image,
        org_name=org_name,
        user_name=user_name,
        username=username
    )

def format_mail_calendar_reminder_email(title, start, end, description, action_url, unsubscribe_url, user_name, org_name, base64_image):
    event_name = title
    event_start = start.astimezone(timezone.get_current_timezone()).strftime('%d.%m.%Y %H:%M') if start else ''
    event_end = end.astimezone(timezone.get_current_timezone()).strftime('%d.%m.%Y %H:%M') if end else ''
    event_description = description if description else ''

    event_description_html = f'<p style="margin: 5px 0;"><span style="color: #666666;">Beschreibung:</span> {event_description}</p>' if event_description else ''

    return mail_calendar_reminder_email_template.format(
        event_name=event_name,
        event_start=event_start,
        event_end=event_end,
        event_description_html=event_description_html,
        action_url=action_url,
        unsubscribe_url=unsubscribe_url,
        base64_image=base64_image,
        org_name=org_name,
        user_name=user_name
    )

def format_new_post_email(post_title, post_text, author_name, post_date, has_survey, action_url, unsubscribe_url, user_name, org_name, base64_image):
    """Format email for new post notifications"""
    # Format the post date
    formatted_date = post_date.astimezone(timezone.get_current_timezone()).strftime('%d.%m.%Y %H:%M') if post_date else ''
    
    # Add survey information if the post has a survey
    survey_info_html = ''
    if has_survey:
        survey_info_html = '<p style="margin: 5px 0;"><span style="color: #666666; font-weight: 500;">📊 Dieser Post enthält eine Umfrage</span></p>'
    
    # Truncate post text if it's too long for email
    max_length = 300
    truncated_text = post_text if len(post_text) <= max_length else post_text[:max_length] + '...'
    
    return new_post_email_template.format(
        post_title=post_title,
        post_text=truncated_text,
        author_name=author_name,
        post_date=formatted_date,
        survey_info_html=survey_info_html,
        action_url=action_url,
        unsubscribe_url=unsubscribe_url,
        user_name=user_name,
        org_name=org_name,
        base64_image=base64_image
    )


def format_register_email_org(einmalpasswort, action_url, org_name, user_name, username):
    return register_email_org_template.format(
        einmalpasswort=einmalpasswort,
        action_url=action_url,
        org_name=org_name,
        user_name=user_name,
        username=username
    )

def get_logo_base64(org):
    with open(org.logo.path, "rb") as org_logo:
        base64_image = base64.b64encode(org_logo.read()).decode('utf-8')
    return base64_image

def send_aufgaben_email(aufgabe, org):
    # Get the organization logo URL
    action_url = 'https://volunteer.solutions/aufgaben/' + str(aufgabe.aufgabe.id) + "/"
    unsubscribe_url = aufgabe.user.customuser.get_unsubscribe_url()
    base64_image = get_logo_base64(org)
    aufg_name = aufgabe.aufgabe.name
    aufg_deadline = aufgabe.faellig
    aufg_beschreibung = aufgabe.aufgabe.beschreibung if aufgabe.aufgabe.beschreibung else ''
    user_name = f"{aufgabe.user.first_name} {aufgabe.user.last_name}"
    
    email_content = format_aufgaben_email(
        aufgabe_name=aufg_name,
        aufgabe_deadline=aufg_deadline,
        base64_image=base64_image,
        org_name=org.name,
        user_name=user_name,
        action_url=action_url,
        aufgabe_beschreibung=aufg_beschreibung,
        unsubscribe_url=unsubscribe_url
    )   
    
    subject = f'Erinnerung: {aufgabe.aufgabe.name}'

    push_content = f'Die Aufgabe "{aufgabe.aufgabe.name}" ist am {aufgabe.faellig.strftime("%d.%m.%Y")} fällig.'

    send_push_notification_to_user(aufgabe.user, subject, push_content, url=action_url)
    
    from django.core.mail import send_mail
    
    if aufgabe.user.customuser.mail_notifications and send_mail(subject, email_content, settings.SERVER_EMAIL, [aufgabe.user.email], html_message=email_content):
        aufgabe.last_reminder = timezone.now()
        aufgabe.currently_sending = False
        aufgabe.save()
        return True
    
    aufgabe.currently_sending = False
    aufgabe.save()
    return False

def send_new_aufgaben_email(aufgaben, org):
    action_url = 'https://volunteer.solutions/aufgaben/'

    base64_image = get_logo_base64(org)

    email_content = format_new_aufgaben_email(
        aufgaben=aufgaben,
        base64_image=base64_image,
        org_name=org.name,
        user_name=f"{aufgaben[0].user.first_name} {aufgaben[0].user.last_name}",
        action_url=action_url,
        unsubscribe_url=aufgaben[0].user.customuser.get_unsubscribe_url()
    )

    subject = f'Neue Aufgaben: {aufgaben[0].aufgabe.name}... und mehr'
        
    if send_mail(subject, email_content, settings.SERVER_EMAIL, [aufgaben[0].user.email], html_message=email_content):
        for aufgabe in aufgaben:
            aufgabe.last_reminder = timezone.now()
            aufgabe.currently_sending = False
            aufgabe.save()
        return True
    
    for aufgabe in aufgaben:
        aufgabe.currently_sending = False
        aufgabe.save()
    
    return False
