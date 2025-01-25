import smtplib
import ssl
import json
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formatdate

from django.conf import settings

def send_aufgaben_email(aufgabe):
    print("Email sent", aufgabe.id)

def send_mail_smtp(receiver_email, subject, html_content):
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
    except smtplib.SMTPException as e:
        print(f"An error occurred: {e}")