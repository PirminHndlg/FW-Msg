from datetime import timedelta

from django.contrib.auth.models import User
from django.db import models
from Global.models import CustomUser, OrgModel, Einsatzland2, Einsatzstelle2
from django.db.models.signals import post_save, post_delete, pre_delete
from django.dispatch import receiver
from simple_history.models import HistoricalRecords



# Create your models here.
class Freiwilliger(OrgModel):
    user = models.OneToOneField(User, on_delete=models.CASCADE, null=True, blank=True, verbose_name='Benutzer:in')
    einsatzland2 = models.ForeignKey(Einsatzland2, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='Einsatzland')
    einsatzstelle2 = models.ForeignKey(Einsatzstelle2, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='Einsatzstelle')
    start_geplant = models.DateField(blank=True, null=True, verbose_name='Start geplant')
    start_real = models.DateField(blank=True, null=True, verbose_name='Start real')
    ende_geplant = models.DateField(blank=True, null=True, verbose_name='Ende geplant')
    ende_real = models.DateField(blank=True, null=True, verbose_name='Ende real')

    history = HistoricalRecords()
    
    CHECKBOX_ACTION_CHOICES = [
        ('add_to_ehemalige', '<i class="bi bi-person-plus-fill me-1"></i>Zu Ehemaligen hinzufügen', 'Der:Die Freiwillige:r wird zu der zuletzt erstellten Benutzergruppe Ehemalige hinzugefügt.'),
        ('send_registration_mail', '<i class="bi bi-envelope-fill me-1"></i>Registrierungsmail')
    ]
    
    def checkbox_action(self, org, checkbox_submit_value):
        if checkbox_submit_value == self.CHECKBOX_ACTION_CHOICES[0][0]:
            from Ehemalige.models import Ehemalige
            ehemalige, created = Ehemalige.objects.get_or_create(user=self.user, org=org)
            if created:
                ehemalige.land.add(self.einsatzland2)
            ehemalige.save()
            
            from Global.models import PersonCluster
            ehe_person_cluster = PersonCluster.objects.filter(org=org, view='E').order_by('-id')
            if ehe_person_cluster.exists():
                ehe_person_cluster = ehe_person_cluster.first()
                self.user.customuser.person_cluster = ehe_person_cluster
                self.user.customuser.save()
                self.user.save()
            
            return True
        elif checkbox_submit_value == self.CHECKBOX_ACTION_CHOICES[1][0]:
            self.user.customuser.send_registration_email()
            return True
        return False

    class Meta:
        verbose_name = 'Freiwillige:r'
        verbose_name_plural = 'Freiwillige'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._original_start_real = self.start_real
        self._original_ende_real = self.ende_real

    def has_field_changed(self, field_name):
        """Helper to check if a field has changed."""
        try:
            original_value = getattr(self, f"_original_{field_name}")
            current_value = getattr(self, field_name)
            return original_value != current_value
        except:
            return False
    
    
    def __str__(self):
        if self.user:
            return self.user.first_name + ' ' + self.user.last_name
        else:
            return f'Freiwillige ohne Benutzer:in {self.id}'

