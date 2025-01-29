import os.path

from django.db import models
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.contrib.auth.models import User

# Create your models here.
class Organisation(models.Model):
    name = models.CharField(max_length=100)
    kurzname = models.CharField(max_length=50, blank=True, null=True)
    email = models.EmailField()
    adress = models.TextField(null=True, blank=True)
    telefon = models.CharField(max_length=20, null=True, blank=True)
    website = models.URLField(null=True, blank=True)
    logo = models.ImageField(upload_to='logos/')
    farbe = models.CharField(max_length=7, default='#007bff')

    class Meta:
        verbose_name = 'Organisation'
        verbose_name_plural = 'Organisationen'

    def __str__(self):
        return self.name
    
@receiver(post_save, sender=Organisation)
def create_folder(sender, instance, created, **kwargs):
    if created:
        from Global.models import CustomUser
        from ORG.tasks import send_register_email_task

        path = os.path.join(instance.name)
        os.makedirs(os.path.join('dokument', instance.name), exist_ok=True)

        if instance.kurzname:
            user_name = instance.kurzname.lower().replace(' ', '_')
        else:
            user_name = instance.name.lower().replace(' ', '_')

        user = User.objects.create(username=user_name, email=instance.email)

        import random
        import string
        
        # Generate random string with letters and digits
        random_password = ''.join(random.choices(string.ascii_letters + string.digits, k=20))
        einmalpasswort = random.randint(10000000, 99999999)
        user.set_password(random_password)
        user.save()

        customuser = CustomUser.objects.create(user=user, org=instance, role='O', einmalpasswort=einmalpasswort)

        send_register_email_task.s(customuser.id).apply_async(countdown=10)


class MailBenachrichtigungen(models.Model):
    org = models.ForeignKey(Organisation, on_delete=models.CASCADE)
    betreff = models.CharField(max_length=100)
    text = models.TextField()

    class Meta:
        verbose_name = 'Mail Benachrichtigung'
        verbose_name_plural = 'Mail Benachrichtigungen'

    def __str__(self):
        return f'{self.organisation} - {self.betreff}'


class Ordner(models.Model):
    org = models.ForeignKey(Organisation, on_delete=models.CASCADE)
    ordner_name = models.CharField(max_length=100)
    def __str__(self):
        return self.ordner_name


@receiver(post_save, sender=Ordner)
def create_folder(sender, instance, **kwargs):
    path = os.path.join(instance.ordner_name)
    os.makedirs(os.path.join('dokument', instance.org.name, path), exist_ok=True)


@receiver(post_delete, sender=Ordner)
def remove_folder(sender, instance, **kwargs):
    path = os.path.join(instance.ordner_name)
    path = os.path.join('dokument', instance.org.name, path)
    if os.path.isdir(path):
        os.rmdir(path)


def upload_to_folder(instance, filename):
    order = instance.ordner
    path = os.path.join(order.ordner_name, filename)
    return os.path.join('dokument', instance.org.name, path)

class Dokument(models.Model):
    org = models.ForeignKey(Organisation, on_delete=models.CASCADE)
    ordner = models.ForeignKey(Ordner, on_delete=models.CASCADE)
    dokument = models.FileField(upload_to=upload_to_folder, null=True, blank=True)
    link = models.URLField(null=True, blank=True)
    date_created = models.DateTimeField(auto_now_add=True)
    date_modified = models.DateTimeField(auto_now=True)
    titel = models.CharField(max_length=100, null=True, blank=True)
    beschreibung = models.TextField(null=True, blank=True)
    fw_darf_bearbeiten = models.BooleanField(default=True)

    def __str__(self):
        return self.titel or self.dokument.name or self.link

    def get_document_type(self):
        if self.dokument:
            import mimetypes
            file_path = self.dokument.path
            # Guess the MIME type based on file extension
            mime_type, _ = mimetypes.guess_type(file_path)

            return mime_type or 'unknown'
        else:
            return 'unknown'


@receiver(post_delete, sender=Dokument)
def remove_file(sender, instance, **kwargs):
    if instance.dokument and os.path.isfile(instance.dokument.path):
        os.remove(instance.dokument.path)