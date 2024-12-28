import os
from datetime import timedelta

from PIL import Image  # Make sure this is from PIL, not Django models
from django.contrib.auth.models import User, AbstractUser
from django.db import models
from ORG.models import Organisation
from django.db.models.signals import post_save, post_delete, pre_delete
from django.dispatch import receiver


# class Organisation(models.Model):
#     name = models.CharField(max_length=100)
#     kurzname = models.CharField(max_length=50, blank=True, null=True)
#     logo = models.ImageField(upload_to='logos/', blank=True, null=True)
#     strasse = models.CharField(max_length=100, blank=True, null=True)
#     plz = models.CharField(max_length=10, blank=True, null=True)
#     ort = models.CharField(max_length=100, blank=True, null=True)
#     email = models.EmailField(max_length=100, blank=True, null=True)
#
#     def __str__(self):
#         return self.name

# @receiver(post_save, sender=User)
# def post_save_user_handler(sender, instance, created, **kwargs):
#     if created:
#         CustomUser.objects.create(user=instance, org=sender.org)

class CustomUser(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    org = models.ForeignKey(Organisation, on_delete=models.CASCADE, verbose_name='Organisation')

    def __str__(self):
        return self.user.username


class Entsendeform(models.Model):
    org = models.ForeignKey(Organisation, on_delete=models.CASCADE, verbose_name='Organisation')
    name = models.CharField(max_length=50, verbose_name='Entsendeform-Name')

    class Meta:
        verbose_name = 'Entsendeform'
        verbose_name_plural = 'Entsendeformen'

    def __str__(self):
        return self.name


class Kirchenzugehoerigkeit(models.Model):
    org = models.ForeignKey(Organisation, on_delete=models.CASCADE, verbose_name='Organisation')
    name = models.CharField(max_length=50, verbose_name='Kirchenzugehoerigkeit-Name')

    class Meta:
        verbose_name = 'Kirchenzugehörigkeit'
        verbose_name_plural = 'Kirchenzugehörigkeiten'

    def __str__(self):
        return self.name


class Einsatzland(models.Model):
    org = models.ForeignKey(Organisation, on_delete=models.CASCADE, verbose_name='Organisation')
    name = models.CharField(max_length=50, verbose_name='Einsatzland')

    class Meta:
        verbose_name = 'Einsatzland'
        verbose_name_plural = 'Einsatzländer'

    def __str__(self):
        return self.name


class Einsatzstelle(models.Model):
    org = models.ForeignKey(Organisation, on_delete=models.CASCADE, verbose_name='Organisation')
    name = models.CharField(max_length=50, verbose_name='Einsatzstelle')
    land = models.ForeignKey(Einsatzland, on_delete=models.CASCADE, verbose_name='Einsatzland')

    class Meta:
        verbose_name = 'Einsatzstelle'
        verbose_name_plural = 'Einsatzstellen'

    def __str__(self):
        return self.name


class Jahrgang(models.Model):
    org = models.ForeignKey(Organisation, on_delete=models.CASCADE, verbose_name='Organisation')
    name = models.CharField(max_length=50, verbose_name='Jahrgang')
    start = models.DateField(verbose_name='Startdatum')
    ende = models.DateField(verbose_name='Enddatum')

    class Meta:
        verbose_name = 'Jahrgang'
        verbose_name_plural = 'Jahrgänge'

    def __str__(self):
        return self.name


# Create your models here.
class Freiwilliger(models.Model):
    GESCHLECHT_CHOICES = [
        ('M', 'Männlich'),
        ('W', 'Weiblich'),
        ('D', 'Divers'),
        ('N', 'Keine Angabe')
    ]

    org = models.ForeignKey(Organisation, on_delete=models.CASCADE, verbose_name='Organisation')
    jahrgang = models.ForeignKey(Jahrgang, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='Jahrgang')
    user = models.OneToOneField(User, on_delete=models.DO_NOTHING, null=True, blank=True, verbose_name='Benutzer')
    first_name = models.CharField(max_length=50, verbose_name='Vorname')
    last_name = models.CharField(max_length=50, verbose_name='Nachname')
    geschlecht = models.CharField(max_length=1, blank=True, null=True, choices=GESCHLECHT_CHOICES, verbose_name='Geschlecht')
    geburtsdatum = models.DateField(blank=True, null=True, verbose_name='Geburtsdatum')
    strasse = models.CharField(max_length=100, blank=True, null=True, verbose_name='Straße')
    plz = models.CharField(max_length=10, blank=True, null=True, verbose_name='PLZ')
    ort = models.CharField(max_length=100, blank=True, null=True, verbose_name='Ort')
    email = models.EmailField(max_length=100, blank=True, null=True, verbose_name='E-Mail')
    phone = models.CharField(max_length=20, blank=True, null=True, verbose_name='Telefon')
    phone_einsatzland = models.CharField(max_length=20, blank=True, null=True, verbose_name='Telefon Einsatzland')
    entsendeform = models.ForeignKey(Entsendeform, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='Entsendeform')
    kirchenzugehoerigkeit = models.ForeignKey(Kirchenzugehoerigkeit, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='Kirchenzugehörigkeit')
    start_geplant = models.DateField(blank=True, null=True, verbose_name='Start geplant')
    start_real = models.DateField(blank=True, null=True, verbose_name='Start real')
    ende_geplant = models.DateField(blank=True, null=True, verbose_name='Ende geplant')
    ende_real = models.DateField(blank=True, null=True, verbose_name='Ende real')

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

    def __str__(self):
        return self.first_name + ' ' + self.last_name


@receiver(post_save, sender=Freiwilliger)
def post_save_handler(sender, instance, created, **kwargs):
    if created:
        # Create username by combining first and last names
        default_username = f"{instance.first_name.replace(' ', '')[:4].lower()}{instance.last_name.split(' ')[-1][:4].lower()}"
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

        custom_user = CustomUser.objects.create(user=user, org=instance.org)
        custom_user.save()

    else:
        if instance.has_field_changed('ende_real'):
            tasks = FreiwilligerAufgaben.objects.filter(freiwilliger=instance, faellig__isnull=False,
                                                        aufgabe__faellig_tage_vor_ende__gt=0)
            for task in tasks:
                task.faellig = instance.ende_real - timedelta(days=task.aufgabe.faellig_tage_vor_ende)
                task.save()
        if instance.has_field_changed('start_real'):
            tasks = FreiwilligerAufgaben.objects.filter(freiwilliger=instance, faellig__isnull=False,
                                                        aufgabe__faellig_tage_nach_start__gt=0)
            for task in tasks:
                task.faellig = instance.start_real + timedelta(days=task.aufgabe.faellig_tage_nach_start)
                task.save()


@receiver(post_delete, sender=Freiwilliger)
def post_delete_handler(sender, instance, **kwargs):
    instance.user.delete()


class Notfallkontakt(models.Model):
    org = models.ForeignKey(Organisation, on_delete=models.CASCADE, verbose_name='Organisation')
    first_name = models.CharField(max_length=50, verbose_name='Vorname')
    last_name = models.CharField(max_length=50, verbose_name='Nachname')
    phone = models.CharField(max_length=20, blank=True, null=True, verbose_name='Telefon')
    email = models.EmailField(max_length=100, blank=True, null=True, verbose_name='E-Mail')
    freiwilliger = models.ForeignKey(Freiwilliger, on_delete=models.CASCADE, verbose_name='Freiwillige:r')

    class Meta:
        verbose_name = 'Notfallkontakt'
        verbose_name_plural = 'Notfallkontakte'

    def __str__(self):
        return self.first_name + ' ' + self.last_name


class Ampel(models.Model):
    CHOICES = [
        ('G', 'Grün'),
        ('Y', 'Gelb'),
        ('R', 'Rot'),
    ]

    org = models.ForeignKey(Organisation, on_delete=models.CASCADE, verbose_name='Organisation')
    freiwilliger = models.ForeignKey(Freiwilliger, on_delete=models.CASCADE, verbose_name='Freiwillige:r')
    status = models.CharField(max_length=1, choices=CHOICES, verbose_name='Ampelmeldung')
    comment = models.TextField(blank=True, null=True, verbose_name='Kommentar')
    date = models.DateTimeField(auto_now_add=True, verbose_name='Datum')

    class Meta:
        verbose_name = 'Ampel'
        verbose_name_plural = 'Ampeln'

    def __str__(self):
        return self.freiwilliger.first_name + ' ' + self.freiwilliger.last_name + ' - ' + self.status


class Aufgabenprofil(models.Model):
    org = models.ForeignKey(Organisation, on_delete=models.CASCADE, verbose_name='Organisation')
    name = models.CharField(max_length=50, verbose_name='Aufgabenprofil-Name')
    beschreibung = models.TextField(null=True, blank=True, verbose_name='Beschreibung')
    einsatzland = models.ForeignKey(Einsatzland, on_delete=models.CASCADE, null=True, blank=True, verbose_name='Einsatzland')
    einsatzstelle = models.ForeignKey(Einsatzstelle, on_delete=models.CASCADE, null=True, blank=True, verbose_name='Einsatzstelle')

    class Meta:
        verbose_name = 'Aufgabenprofil'
        verbose_name_plural = 'Aufgabenprofile'

    def __str__(self):
        return self.name


class FreiwilligerAufgaben(models.Model):
    WIEDERHOLUNG_CHOICES = [
        ('T', 'Täglich'),
        ('W', 'Wöchentlich'),
        ('M', 'Monatlich'),
        ('J', 'Jährlich'),
        ('N', 'Nicht wiederholen')
    ]

    org = models.ForeignKey(Organisation, on_delete=models.CASCADE, verbose_name='Organisation')
    freiwilliger = models.ForeignKey(Freiwilliger, on_delete=models.CASCADE, verbose_name='Freiwillige:r')
    aufgabe = models.ForeignKey('Aufgabe', on_delete=models.CASCADE, verbose_name='Aufgabe')
    erledigt = models.BooleanField(default=False, verbose_name='Erledigt')
    pending = models.BooleanField(default=False, verbose_name='Wird bearbeitet')
    datetime = models.DateTimeField(auto_now_add=True, verbose_name='Erstellt am')
    faellig = models.DateField(blank=True, null=True, verbose_name='Fällig am')
    erledigt_am = models.DateField(blank=True, null=True, verbose_name='Erledigt am')
    wiederholung = models.CharField(max_length=1, choices=WIEDERHOLUNG_CHOICES, default='N', verbose_name='Wiederholung')
    wiederholung_ende = models.DateField(blank=True, null=True, verbose_name='Wiederholung bis')

    def save(self, *args, **kwargs):
        print(self.wiederholung, self.wiederholung_ende)
        if self.wiederholung != 'N' and not self.wiederholung_ende:
            self.wiederholung_ende = self.freiwilliger.ende_geplant
        if not self.faellig:

            if self.aufgabe.faellig_tage_nach_start:
                self.faellig = self.freiwilliger.start_geplant + timedelta(days=self.aufgabe.faellig_tage_nach_start)
            elif self.aufgabe.faellig_tage_vor_ende:
                self.faellig = self.freiwilliger.ende_geplant - timedelta(days=self.aufgabe.faellig_tage_vor_ende)
            else:
                self.faellig = self.aufgabe.faellig

            # if self.aufgabe.faellig:
            #     self.faellig = self.aufgabe.faellig
        super(FreiwilligerAufgaben, self).save(*args, **kwargs)

    class Meta:
        verbose_name = 'Freiwilliger Aufgabe'
        verbose_name_plural = 'Freiwilliger Aufgaben'

    def __str__(self):
        return self.freiwilliger.first_name + ' ' + self.freiwilliger.last_name + ' - ' + self.aufgabe.name


class FreiwilligerUpload(models.Model):
    org = models.ForeignKey(Organisation, on_delete=models.CASCADE, verbose_name='Organisation')
    freiwilligeraufgabe = models.ForeignKey(FreiwilligerAufgaben, on_delete=models.CASCADE, verbose_name='Freiwillige:r Aufgabe')
    file = models.FileField(upload_to='uploads/', verbose_name='Datei')
    datetime = models.DateTimeField(auto_now_add=True, verbose_name='Erstellt am')

    class Meta:
        verbose_name = 'Freiwilliger Upload'
        verbose_name_plural = 'Freiwilliger Uploads'

    def __str__(self):
        return self.file.name


# @receiver(post_delete, sender=FreiwilligerUpload)
# def post_delete_handler(sender, instance, **kwargs):
#     instance.file.delete(False)
#     os.remove(instance.file.path)

class FreiwilligerFotos(models.Model):
    org = models.ForeignKey(Organisation, on_delete=models.CASCADE, verbose_name='Organisation')
    freiwilliger = models.ForeignKey(Freiwilliger, on_delete=models.CASCADE, verbose_name='Freiwillige:r')
    file = models.ImageField(upload_to='fotos/', verbose_name='Foto')
    datetime = models.DateTimeField(auto_now_add=True, verbose_name='Erstellt am')

    class Meta:
        verbose_name = 'Freiwilliger Foto'
        verbose_name_plural = 'Freiwilliger Fotos'

    def __str__(self):
        return self.file.name


class FreiwilligerAufgabenprofil(models.Model):
    # org = models.ForeignKey(Organisation, on_delete=models.CASCADE)
    freiwilliger = models.ForeignKey(Freiwilliger, on_delete=models.CASCADE, verbose_name='Freiwillige:r')
    aufgabenprofil = models.ForeignKey(Aufgabenprofil, on_delete=models.CASCADE, verbose_name='Aufgabenprofil')

    class Meta:
        verbose_name = 'Freiwilliger Aufgabenprofil'
        verbose_name_plural = 'Freiwilliger Aufgabenprofile'

    def __str__(self):
        return self.freiwilliger.first_name + ' ' + self.freiwilliger.last_name + ' - ' + self.aufgabenprofil.name


@receiver(post_save, sender=FreiwilligerAufgabenprofil)
def post_save_handler(sender, instance, **kwargs):
    aufgaben = AufgabenprofilAufgabe.objects.filter(aufgabenprofil=instance.aufgabenprofil)
    for aufgabe in aufgaben:
        aufg = FreiwilligerAufgaben.objects.get_or_create(freiwilliger=instance.freiwilliger, aufgabe=aufgabe.aufgabe)
        if not aufg.faeillig:
            if aufgabe.aufgabe.faellig_tage_nach_start:
                aufg.faellig = instance.freiwilliger.start_geplant + timedelta(days=aufgabe.aufgabe.faellig_tage_nach_start)
            elif aufgabe.aufgabe.faellig_tage_vor_ende:
                aufg.faellig = instance.freiwilliger.ende_geplant - timedelta(days=aufgabe.aufgabe.faellig_tage_vor_ende)
            else:
                aufg.faellig = aufgabe.aufgabe.faellig


@receiver(pre_delete, sender=FreiwilligerAufgabenprofil)
def post_delete_handler(sender, instance, **kwargs):
    aufgaben = AufgabenprofilAufgabe.objects.filter(aufgabenprofil=instance.aufgabenprofil)
    for aufgabe in aufgaben:
        FreiwilligerAufgaben.objects.filter(freiwilliger=instance.freiwilliger, aufgabe=aufgabe.aufgabe).delete()


class Aufgabe(models.Model):
    org = models.ForeignKey(Organisation, on_delete=models.CASCADE, verbose_name='Organisation')
    name = models.CharField(max_length=50, verbose_name='Aufgabenname')
    beschreibung = models.TextField(null=True, blank=True, verbose_name='Beschreibung')
    mitupload = models.BooleanField(default=False, verbose_name='Upload möglich')
    faellig = models.DateField(blank=True, null=True, verbose_name='Fällig am')
    faellig_tage_nach_start = models.IntegerField(blank=True, null=True, verbose_name='Fällig Tage nach Einsatzstart')
    faellig_tage_vor_ende = models.IntegerField(blank=True, null=True, verbose_name='Fällig Tage vor Einsatzende')

    class Meta:
        verbose_name = 'Aufgabe'
        verbose_name_plural = 'Aufgaben'

    def __str__(self):
        return self.name


class AufgabenprofilAufgabe(models.Model):
    # org = models.ForeignKey(Organisation, on_delete=models.CASCADE)
    aufgabenprofil = models.ForeignKey(Aufgabenprofil, on_delete=models.CASCADE, verbose_name='Aufgabenprofil')
    aufgabe = models.ForeignKey(Aufgabe, on_delete=models.CASCADE, verbose_name='Aufgabe')

    class Meta:
        verbose_name = 'Aufgabenprofil Aufgabe'
        verbose_name_plural = 'Aufgabenprofil Aufgaben'

    def __str__(self):
        return self.aufgabenprofil.name + ' - ' + self.aufgabe.name


class Post(models.Model):
    org = models.ForeignKey(Organisation, on_delete=models.CASCADE, verbose_name='Organisation')
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='Benutzer')
    title = models.CharField(max_length=50, verbose_name='Posttitel')
    text = models.TextField(verbose_name='Text')
    date = models.DateTimeField(auto_now_add=True, verbose_name='Datum')

    class Meta:
        verbose_name = 'Post'
        verbose_name_plural = 'Posts'

    def __str__(self):
        return self.title


@receiver(post_save, sender=Post)
def post_save_handler(sender, instance, **kwargs):
    if instance.org:
        pass


class Bilder(models.Model):
    org = models.ForeignKey(Organisation, on_delete=models.CASCADE, verbose_name='Organisation')
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='Benutzer')
    titel = models.CharField(max_length=50, verbose_name='Bildtitel')
    beschreibung = models.TextField(blank=True, null=True, verbose_name='Beschreibung')
    date_created = models.DateTimeField(auto_now_add=True, verbose_name='Erstellt am')
    date_updated = models.DateTimeField(auto_now=True, verbose_name='Aktualisiert am')

    class Meta:
        verbose_name = 'Bild'
        verbose_name_plural = 'Bilder'

    def __str__(self):
        return self.titel


class BilderGallery(models.Model):
    org = models.ForeignKey(Organisation, on_delete=models.CASCADE, verbose_name='Organisation')
    image = models.ImageField(upload_to='bilder/', verbose_name='Bild')

    small_image = models.ImageField(upload_to='bilder/small/', blank=True, null=True, verbose_name='Kleines Bild')
    bilder = models.ForeignKey(Bilder, on_delete=models.CASCADE, verbose_name='Bild')

    class Meta:
        verbose_name = 'Bilder Gallery'
        verbose_name_plural = 'Bilder Galleries'

    def __str__(self):
        return self.image.name


# def get_smaller_image(image):
#     print('get_smaller_image')
#     from PIL import Image
#     import io
#     from django.core.files.base import ContentFile
#
#     img = Image.open(image)
#     img.thumbnail((600, 600))
#
#     img_io = io.BytesIO()
#     format = img.format if img.format in ["JPEG", "PNG"] else "JPEG"
#     img.save(img_io, format=format)
#     extension = format.lower()
#     filename = f"{image.name.rsplit('.', 1)[0]}.{extension}"
#     filename.replace('bilder/', '')
#     print(filename)
#     return ContentFile(img_io.getvalue(), name=image.name)
#
#
# @receiver(post_save, sender=BilderGallery)
# def post_save_handler(sender, instance, **kwargs):
#     instance.small_image = get_smaller_image(instance.image)


class ProfilUser(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='Benutzer')
    attribut = models.CharField(max_length=50, verbose_name='Attribut')
    value = models.TextField(verbose_name='Wert')

    class Meta:
        verbose_name = 'Profil User'
        verbose_name_plural = 'Profil User'

    def __str__(self):
        return self.user + self.attribut
