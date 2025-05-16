from django.db import models
from Global.models import OrgModel
from django.contrib.auth.models import User

# Create your models here.
class Bewerber(OrgModel):
    STATUS_CHOICES = [
        ('green', 'Grün'),
        ('yellow', 'Gelb'),
        ('red', 'Rot'),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, verbose_name='Benutzer:in')
    status = models.CharField(verbose_name='Status', max_length=20, choices=STATUS_CHOICES, null=True, blank=True)
    abgeschlossen = models.BooleanField(verbose_name='Abgeschlossen', default=False)
    abgeschlossen_am = models.DateTimeField(verbose_name='Abgeschlossen am', null=True, blank=True)
    verification_token = models.CharField(verbose_name='Verifikationstoken', max_length=255, null=True, blank=True)

    def __str__(self):
        return self.user.first_name + ' ' + self.user.last_name

class ApplicationQuestion(OrgModel):
    ANSWER_TYPE_CHOICES = [
        ('t', 'Text'),
        ('f', 'Datei'),
    ]
    question = models.TextField(verbose_name='Frage')
    order = models.IntegerField(verbose_name='Reihenfolge', null=True, blank=True)
    max_length = models.IntegerField(verbose_name='Maximale Länge', default=1000, null=True, blank=True)
    
    def __str__(self):
        return self.question

    def save(self, *args, **kwargs):
        if not self.order:
            max_order = ApplicationQuestion.objects.filter(org=self.org).aggregate(models.Max('order'))['order__max'] or 0
            self.order = max_order + 1
        super().save(*args, **kwargs)
    
    class Meta:
        ordering = ['order']
        
        

class ApplicationAnswer(OrgModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='Benutzer:in')
    question = models.ForeignKey(ApplicationQuestion, on_delete=models.CASCADE, verbose_name='Frage')
    answer = models.TextField(verbose_name='Antwort', null=True, blank=True)
    
    def __str__(self):
        return self.answer

class ApplicationText(OrgModel):
    welcome = models.TextField(verbose_name='Begrüßung')
    footer = models.TextField(verbose_name='Fußzeile')
    deadline = models.DateField(verbose_name='Abgabefrist', null=True, blank=True)

    def __str__(self):
        return self.org.name
    
class ApplicationFileQuestion(OrgModel):
    name = models.CharField(verbose_name='Name', max_length=255)
    description = models.TextField(verbose_name='Beschreibung', null=True, blank=True)
    order = models.IntegerField(verbose_name='Reihenfolge', null=True, blank=True)
    
    def save(self, *args, **kwargs):
        if not self.order:
            max_order = ApplicationFileQuestion.objects.filter(org=self.org).aggregate(models.Max('order'))['order__max'] or 0
            self.order = max_order + 1
        super().save(*args, **kwargs)
    
    class Meta:
        ordering = ['order']
    
    def __str__(self):
        return self.org.name
    
class ApplicationAnswerFile(OrgModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='Benutzer:in')
    file_question = models.ForeignKey(ApplicationFileQuestion, on_delete=models.CASCADE, verbose_name='Datei')
    file = models.FileField(verbose_name='Datei', upload_to='bewerbung/', null=True, blank=True)
    
    def __str__(self):
        return self.org.name
