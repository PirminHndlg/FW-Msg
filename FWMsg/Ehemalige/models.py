from django.db import models
from Global.models import OrgModel, Einsatzland2
from django.contrib.auth.models import User

# Create your models here.
class Ehemalige(OrgModel):
    user = models.OneToOneField(User, on_delete=models.CASCADE, null=True, blank=True, verbose_name='Benutzer:in')
    land = models.ManyToManyField(Einsatzland2, verbose_name='Länder', null=True, blank=True)

    CHECKBOX_ACTION_CHOICES = [
        ('send_registration_mail', '<i class="bi bi-envelope-fill me-1"></i>Registrierungsmail'),
    ]

    def checkbox_action(self, org, checkbox_submit_value):
        if checkbox_submit_value == self.CHECKBOX_ACTION_CHOICES[0][0]:
            self.user.customuser.send_registration_email()
            return True
        return False

    class Meta:
        verbose_name = 'Ehemalige'
        verbose_name_plural = 'Ehemalige'

    def __str__(self):
        if self.user:
            return f"{self.user.first_name} {self.user.last_name}".strip() or self.user.username
        return "Ehemalige (No User)"