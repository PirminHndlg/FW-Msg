from django.db import models
from Global.models import OrgModel, PersonCluster, Einsatzland2
from django.utils.translation import gettext_lazy as _


class OwnSigninUser(OrgModel):
    first_name = models.CharField(max_length=255, verbose_name=_('Vorname'))
    last_name = models.CharField(max_length=255, verbose_name=_('Nachname'))
    email = models.EmailField(max_length=255, verbose_name=_('E-Mail'))
    person_cluster = models.ForeignKey(PersonCluster, on_delete=models.CASCADE, verbose_name=_('Benutzergruppe'))
    land = models.ForeignKey(
        Einsatzland2,
        on_delete=models.CASCADE,
        verbose_name=_('Land'),
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_('Erstellt am'), null=True, blank=True)
    
    class Meta:
        verbose_name = _('Eigenes Registrieren')
        verbose_name_plural = _('Eigenes Registrieren')
        
    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.email})"