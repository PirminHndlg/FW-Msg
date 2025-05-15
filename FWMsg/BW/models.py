from django.db import models
from Global.models import OrgModel
from django.contrib.auth.models import User

# Create your models here.
class Bewerber(OrgModel):
    user = models.OneToOneField(User, on_delete=models.CASCADE, verbose_name='Benutzer:in')
    abgeschlossen = models.BooleanField(verbose_name='Abgeschlossen', default=False)
    abgeschlossen_am = models.DateTimeField(verbose_name='Abgeschlossen am', null=True, blank=True)

    def __str__(self):
        return self.user.first_name + ' ' + self.user.last_name

class ApplicationQuestion(OrgModel):
    question = models.TextField(verbose_name='Frage')
    order = models.IntegerField(verbose_name='Reihenfolge')
    max_length = models.IntegerField(verbose_name='Maximale Länge', default=255, null=True, blank=True)
    
    def __str__(self):
        return self.question

class ApplicationAnswer(OrgModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='Benutzer:in')
    question = models.ForeignKey(ApplicationQuestion, on_delete=models.CASCADE, verbose_name='Frage')
    answer = models.TextField(verbose_name='Antwort', null=True, blank=True)

    def __str__(self):
        return self.answer

class ApplicationText(OrgModel):
    welcome = models.TextField(verbose_name='Begrüßung')
    footer = models.TextField(verbose_name='Fußzeile')

    def __str__(self):
        return self.org.name