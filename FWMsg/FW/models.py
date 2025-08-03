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

