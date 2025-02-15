from django.db import models
from django.contrib.auth.models import User
from ORG.models import Organisation
from django.dispatch import receiver
from django.db.models.signals import post_save
import random
from django.db import models
from FWMsg.middleware import get_current_request



class OrgManager(models.Manager):
    def get_queryset(self):
        request = get_current_request()
        if request and hasattr(request, 'user') and hasattr(request.user, 'org'):
            return super().get_queryset().filter(org=request.user.org)
        return super().get_queryset()


class OrgModel(models.Model):
    org = models.ForeignKey(Organisation, on_delete=models.CASCADE, verbose_name='Organisation')
    objects = OrgManager()

    class Meta:
        abstract = True

# Create your models here.
class CustomUser(models.Model):
    ROLE_CHOICES = [
        ('A', 'Admin'),
        ('O', 'Organisation'),
        ('F', 'Freiwillige:r'),
        ('R', 'Referent:in'),
        ('E', 'Ehemalige:r'),
        ('T', 'Team')
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, verbose_name='Benutzer:in')
    org = models.ForeignKey(Organisation, on_delete=models.CASCADE, verbose_name='Organisation')
    role = models.CharField(max_length=1, choices=ROLE_CHOICES, default='F', verbose_name='Rolle')
    profil_picture = models.ImageField(upload_to='profil_picture/', blank=True, null=True, verbose_name='Profilbild')

    einmalpasswort = models.CharField(max_length=20, blank=True, null=True, verbose_name='Einmalpasswort')

    def send_registration_email(self):
        if not self.einmalpasswort:
            self.einmalpasswort = random.randint(100000, 999999)
            self.save()

        if self.role == 'F':
            from FW.tasks import send_register_email_task
            from FW.models import Freiwilliger
            freiwilliger = Freiwilliger.objects.get(user=self.user)
            send_register_email_task.s(freiwilliger.id).apply_async(countdown=10)
        elif self.role == 'O':
            from ORG.tasks import send_register_email_task
            send_register_email_task.s(self.id).apply_async(countdown=10)
    
    def __str__(self):
        return self.user.username
    
    class Meta:
        verbose_name = 'Benutzer:in'
        verbose_name_plural = 'Benutzer:innen'

    
@receiver(post_save, sender=CustomUser)
def post_save_handler(sender, instance, created, **kwargs):
    from FW.models import calculate_small_image

    if instance.profil_picture and not hasattr(instance, '_processing_profil_picture'):
        instance._processing_profil_picture = True
        instance.profil_picture = calculate_small_image(instance.profil_picture)
        instance.save()
        delattr(instance, '_processing_profil_picture')

# Add property to User model to access org
User.add_to_class('org', property(lambda self: self.customuser.org if hasattr(self, 'customuser') else None))
User.add_to_class('role', property(lambda self: self.customuser.role if hasattr(self, 'customuser') else None))

class Feedback(models.Model):
    text = models.TextField(verbose_name='Feedback')
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='User', null=True, blank=True)
    anonymous = models.BooleanField(default=False, verbose_name='Anonym')

    def __str__(self):
        return f'Feedback von {self.user.username}' if not self.anonymous and self.user else 'Anonymes Feedback'

@receiver(post_save, sender=Feedback)
def post_save_handler(sender, instance, created, **kwargs):
    if instance.anonymous and instance.user:
        instance.user = None
        instance.save()
    
    if created:
        from ORG.tasks import send_feedback_email_task
        send_feedback_email_task.s(instance.id).apply_async(countdown=10)

class KalenderEvent(OrgModel):
    user = models.ManyToManyField(User, verbose_name='Benutzer:in')
    title = models.CharField(max_length=255, verbose_name='Titel')
    start = models.DateTimeField(verbose_name='Start')
    end = models.DateTimeField(verbose_name='Ende', null=True, blank=True)
    description = models.TextField(verbose_name='Beschreibung', null=True, blank=True)

class Log(models.Model):
    LEVEL_CHOICES = [
        ('DEBUG', 'Debug'),
        ('INFO', 'Info'),
        ('WARNING', 'Warning'),
        ('ERROR', 'Error'),
        ('CRITICAL', 'Critical'),
    ]

    timestamp = models.DateTimeField(auto_now_add=True, verbose_name='Timestamp')
    level = models.CharField(max_length=10, choices=LEVEL_CHOICES, default='INFO', verbose_name='Level')
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='User')
    message = models.TextField(verbose_name='Message')
    source = models.CharField(max_length=100, verbose_name='Source')
    trace = models.TextField(blank=True, null=True, verbose_name='Stack Trace')

    class Meta:
        verbose_name = 'Log Entry'
        verbose_name_plural = 'Log Entries'
        ordering = ['-timestamp']

    def __str__(self):
        return f"[{self.timestamp}] {self.level}: {self.message}"
