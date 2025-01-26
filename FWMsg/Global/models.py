from django.db import models
from django.contrib.auth.models import User
from ORG.models import Organisation
from django.dispatch import receiver
from django.db.models.signals import post_save

# Create your models here.
class CustomUser(models.Model):
    ROLE_CHOICES = [
        ('A', 'Admin'),
        ('O', 'Organisation'),
        ('T', 'Team'),
        ('F', 'Freiwillige:r'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE)
    org = models.ForeignKey(Organisation, on_delete=models.CASCADE, verbose_name='Organisation')
    role = models.CharField(max_length=1, choices=ROLE_CHOICES, default='F', verbose_name='Rolle')
    profil_picture = models.ImageField(upload_to='profil_picture/', blank=True, null=True, verbose_name='Profilbild')

    einmalpasswort = models.CharField(max_length=20, blank=True, null=True, verbose_name='Einmalpasswort')
    
    def __str__(self):
        return self.user.username
    
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
