from django.db import models
from Global.models import OrgModel, Einsatzland2
from django.contrib.auth.models import User

# Create your models here.
class Ehemalige(OrgModel):
    user = models.OneToOneField(User, on_delete=models.CASCADE, null=True, blank=True, verbose_name='Benutzer:in')
    land = models.ManyToManyField(Einsatzland2, verbose_name='Länder')

    class Meta:
        verbose_name = 'Ehemalige'
        verbose_name_plural = 'Ehemalige'

    def __str__(self):
        if self.user:
            return f"{self.user.first_name} {self.user.last_name}".strip() or self.user.username
        return "Ehemalige (No User)"