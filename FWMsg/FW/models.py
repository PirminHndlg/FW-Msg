from datetime import timedelta

from django.contrib.auth.models import User
from django.db import models
from Global.models import CustomUser, OrgModel, Einsatzland2, Einsatzstelle2
from django.db.models.signals import post_save, post_delete, pre_delete
from django.dispatch import receiver
from simple_history.models import HistoricalRecords



# Create your models here.
class Freiwilliger(OrgModel):
    user = models.OneToOneField(User, on_delete=models.DO_NOTHING, null=True, blank=True, verbose_name='Benutzer:in')
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
        original_value = getattr(self, f"_original_{field_name}")
        current_value = getattr(self, field_name)
        return original_value != current_value
    
    def send_register_email(self):
        from FW.tasks import send_register_email_task
        send_register_email_task.delay(self)

    def __str__(self):
        return self.user.first_name + ' ' + self.user.last_name


@receiver(post_save, sender=Freiwilliger)
def post_save_handler(sender, instance, created, **kwargs):
    if created:
        import random

        # Create username by combining first and last names
        default_username = f"{instance.first_name.replace(' ', '-').lower()}"
        username = default_username
        c = 0
        user = True
        while user:
            user = User.objects.filter(username=username).exists()
            if user:
                c += 1
                username = default_username + str(c)

        # Create a User with the username and password set to birthdate
        user = User.objects.create_user(
            username=username,
            password=str(instance.last_name.lower()),  # Ensure password is a string
            email=instance.email  # You can link email to User if needed
        )

        # Link the created User to the Freiwilliger instance
        instance.user = user
        instance.save()

        einmalpasswort = random.randint(100000, 999999)

        custom_user = CustomUser.objects.create(user=user, org=instance.org, einmalpasswort=einmalpasswort)
        custom_user.save()

    else:
        from Global.models import UserAufgaben
        if instance.has_field_changed('ende_real') or instance.has_field_changed('ende_geplant'):
            tasks = UserAufgaben.objects.filter(user=instance.user, faellig__isnull=False,
                                                        aufgabe__faellig_tage_vor_ende__isnull=False, erledigt=False, pending=False)
            start_date = instance.start_real or instance.start_geplant or instance.jahrgang.start
            for task in tasks:
                task.faellig = start_date - timedelta(days=task.aufgabe.faellig_tage_vor_ende)
                task.save()
        if instance.has_field_changed('start_real') or instance.has_field_changed('start_geplant'):
            tasks = UserAufgaben.objects.filter(user=instance.user, faellig__isnull=False,
                                                        aufgabe__faellig_tage_nach_start__isnull=False, erledigt=False, pending=False)
            start_date = instance.start_real or instance.start_geplant or instance.jahrgang.start
            for task in tasks:
                task.faellig = start_date + timedelta(days=task.aufgabe.faellig_tage_nach_start)
                task.save()

    if not instance.user.first_name or not instance.user.last_name:
        instance.user.first_name = instance.first_name
        instance.user.last_name = instance.last_name
        instance.user.save()


@receiver(post_delete, sender=Freiwilliger)
def post_delete_handler(sender, instance, **kwargs):
    instance.user.delete()
