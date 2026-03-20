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
    AUFGABENUEBERSICHT_CHOICES = [
        ('N', 'Keine Aufgabenübersicht'),
        ('L', 'Aufgabenübersicht für Freiwillige mit gleichem Einsatzland'),
        ('A', 'Aufgabenübersicht für alle Freiwillige'),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, null=True, blank=True, verbose_name='Benutzer:in')
    land = models.ManyToManyField(Einsatzland2, verbose_name='Länderzuständigkeit', blank=True)
    aufgabenuebersicht = models.CharField(max_length=1, choices=AUFGABENUEBERSICHT_CHOICES, default='N', verbose_name='Aufgabenübersicht', help_text='Aufgabenübersicht, die für dieses Teammitglied angezeigt werden')
    
    history = HistoricalRecords()

    class Meta:
        verbose_name = 'Teammitglied'
        verbose_name_plural = 'Team'

    def __str__(self):
        if self.user:
            return f"{self.user.first_name} {self.user.last_name}".strip() or self.user.username
        return "Teammitglied (No User)"
