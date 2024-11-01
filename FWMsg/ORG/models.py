from django.db import models

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