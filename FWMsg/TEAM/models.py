from django.db import models
from simple_history.models import HistoricalRecords
from django.dispatch import receiver
import random
import string
from Global.models import OrgModel, Einsatzland2
from django.db.models.signals import post_save
from django.contrib.auth.models import User

# Create your models here.
class Team(OrgModel):
    user = models.OneToOneField(User, on_delete=models.CASCADE, null=True, blank=True, verbose_name='Benutzer:in')
    land = models.ManyToManyField(Einsatzland2, verbose_name='Länderzuständigkeit', blank=True)

    history = HistoricalRecords()

    class Meta:
        verbose_name = 'Teammitglied'
        verbose_name_plural = 'Team'

    def __str__(self):
        return f'{self.user.last_name}, {self.user.first_name}'

@receiver(post_save, sender=Team)
def create_user(sender, instance, **kwargs):
    return
    if not instance.user:
        from Global.models import CustomUser

        default_username = instance.last_name.lower().replace(' ', '_')
        user = User.objects.create(username=default_username, email=instance.email)
        random_password = ''.join(random.choices(string.ascii_letters + string.digits, k=20))
        user.set_password(random_password)
        user.save()
    
        einmalpasswort = random.randint(10000000, 99999999)
        customuser = CustomUser.objects.create(user=user, org=instance.org, role='T', einmalpasswort=einmalpasswort)
        
        instance.user = user
        instance.save()