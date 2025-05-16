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
    
    class Meta:
        ordering = ['user__first_name', 'user__last_name']
        verbose_name = 'Bewerber:in'
        verbose_name_plural = 'Bewerber:innen'

class ApplicationQuestion(OrgModel):
    ANSWER_TYPE_CHOICES = [
        ('t', 'Text'),
        ('f', 'Datei'),
    ]
    question = models.TextField(verbose_name='Frage', help_text='Die Frage, die der Bewerber:in beantworten soll.')
    order = models.IntegerField(verbose_name='Position', null=True, blank=True, help_text='Die Position der Frage in der Bewerbung. Wenn leer, wird hinten eingefügt.')
    max_length = models.IntegerField(verbose_name='Maximale Länge', default=1000, null=True, blank=True, help_text='Die maximale Länge der Antwort.')
    
    def __str__(self):
        return self.question

    def save(self, *args, **kwargs):
        if not self.order:
            max_order = ApplicationQuestion.objects.filter(org=self.org).aggregate(models.Max('order'))['order__max'] or 0
            self.order = max_order + 1
        
        questions_same_order = ApplicationQuestion.objects.filter(org=self.org, order=self.order).exclude(id=self.id)
        if questions_same_order.exists():
            for question in questions_same_order:
                question.order = question.order + 1
                question.save()
        
        super().save(*args, **kwargs)
    
    class Meta:
        ordering = ['order']
        unique_together = ('org', 'order')
        verbose_name = 'Bewerbungsfrage'
        verbose_name_plural = 'Bewerbungsfragen'
        

class ApplicationAnswer(OrgModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='Benutzer:in')
    question = models.ForeignKey(ApplicationQuestion, on_delete=models.CASCADE, verbose_name='Frage', help_text='Die Frage, die der Bewerber:in beantworten soll.')
    answer = models.TextField(verbose_name='Antwort', null=True, blank=True, help_text='Die Antwort, die der Bewerber:in gegeben hat.')
    
    def __str__(self):
        return self.answer
    
    class Meta:
        verbose_name = 'Bewerbungsantwort'
        verbose_name_plural = 'Bewerbungsantworten'

class ApplicationText(OrgModel):
    welcome = models.TextField(verbose_name='Begrüßung', help_text='Die Begrüßung, die der Bewerber:in beim Start der Bewerbung sieht.')
    footer = models.TextField(verbose_name='Fußzeile', help_text='Die Fußzeile, die der Bewerber:in am Ende der Bewerbung sieht.')
    deadline = models.DateField(verbose_name='Abgabefrist', null=True, blank=True, help_text='Die Abgabefrist, bis zu welcher die Bewerbung abgeschlossen werden muss.')

    def __str__(self):
        return self.org.name
    
    class Meta:
        verbose_name = 'Bewerbungstext'
        verbose_name_plural = 'Bewerbungstexte'

class ApplicationFileQuestion(OrgModel):
    ALLOWED_EXTENSIONS = ['.pdf', '.doc', '.docx', '.txt', '.png', '.jpg', '.jpeg']
    
    name = models.CharField(verbose_name='Name', max_length=255, help_text='Der Name der Datei, die der Bewerber:in hochladen muss.')
    description = models.TextField(verbose_name='Beschreibung', null=True, blank=True, help_text='Die Beschreibung der Datei, die der Bewerber:in hochladen muss.')
    order = models.IntegerField(verbose_name='Position', null=True, blank=True, help_text='Die Position der Datei in der Bewerbung. Wenn leer, wird hinten eingefügt.')
    
    def save(self, *args, **kwargs):
        if not self.order:
            max_order = ApplicationFileQuestion.objects.filter(org=self.org).aggregate(models.Max('order'))['order__max'] or 0
            self.order = max_order + 1
        super().save(*args, **kwargs)
    
    def __str__(self):
        return self.org.name
    
    class Meta:
        ordering = ['order']
        verbose_name = 'Bewerbungsdatei'
        verbose_name_plural = 'Bewerbungsdateien'
    
class ApplicationAnswerFile(OrgModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='Benutzer:in')
    file_question = models.ForeignKey(ApplicationFileQuestion, on_delete=models.CASCADE, verbose_name='Datei')
    file = models.FileField(verbose_name='Datei', upload_to='bewerbung/', null=True, blank=True)
    
    def __str__(self):
        return self.org.name
    
    class Meta:
        verbose_name = 'Bewerbungsdatei'
        verbose_name_plural = 'Bewerbungsdateien'
