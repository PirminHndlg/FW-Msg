import os.path

from django.db import models
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver


# Create your models here.
class Organisation(models.Model):
    name = models.CharField(max_length=100)
    kurzname = models.CharField(max_length=50, blank=True, null=True)
    email = models.EmailField(null=True, blank=True)
    adress = models.TextField(null=True, blank=True)
    telefon = models.CharField(max_length=20, null=True, blank=True)
    website = models.URLField(null=True, blank=True)
    logo = models.ImageField(upload_to='logos/', blank=True, null=True)
    farbe = models.CharField(max_length=7, default='#007bff')

    class Meta:
        verbose_name = 'Organisation'
        verbose_name_plural = 'Organisationen'

    def __str__(self):
        return self.name


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
    ober_ordner = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True)
    ordner_name = models.CharField(max_length=100)

    def __str__(self):
        return self.ordner_name


@receiver(post_save, sender=Ordner)
def create_folder(sender, instance, **kwargs):
    order = instance.ober_ordner
    path = os.path.join(instance.ordner_name)
    while order:
        path = os.path.join(order.ordner_name, path)
        order = order.ober_ordner
    os.makedirs(os.path.join(instance.org.name, path), exist_ok=True)


@receiver(post_delete, sender=Ordner)
def remove_folder(sender, instance, **kwargs):
    order = instance.ober_ordner
    path = os.path.join(instance.ordner_name)
    while order:
        path = os.path.join(order.ordner_name, path)
        order = order.ober_ordner
    path = os.path.join(instance.org.name, path)
    if os.path.isdir(path):
        os.rmdir(path)


def upload_to_folder(instance, filename):
    order = instance.ordner
    path = os.path.join(filename)
    while order:
        path = os.path.join(order.ordner_name, path)
        order = order.ober_ordner
    return os.path.join(instance.org.name, path)

class Dokument(models.Model):
    org = models.ForeignKey(Organisation, on_delete=models.CASCADE)
    ordner = models.ForeignKey(Ordner, on_delete=models.CASCADE)
    dokument = models.FileField(upload_to=upload_to_folder)
    date_created = models.DateTimeField(auto_now_add=True)
    beschreibung = models.TextField(null=True, blank=True)

    def __str__(self):
        return self.dokument.name


@receiver(post_delete, sender=Dokument)
def remove_file(sender, instance, **kwargs):
    if os.path.isfile(instance.dokument.path):
        os.remove(instance.dokument.path)
