import os
from datetime import datetime, timedelta

from PIL import Image  # Make sure this is from PIL, not Django models
from django.contrib.auth.models import User, AbstractUser
from django.db import models
from ORG.models import Organisation, JahrgangTyp
from Global.models import CustomUser, OrgModel
from django.db.models.signals import post_save, post_delete, pre_delete
from django.dispatch import receiver
from django.core.files.base import ContentFile
import io



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


def calculate_small_image(image):
    # Open the image
    img = Image.open(image)
            
    # Check for EXIF orientation and rotate if needed
    try:
        exif = img._getexif()
        if exif:
            orientation = exif.get(274)  # 274 is the orientation tag
            if orientation:
                rotate_values = {
                    3: 180,
                    6: 270,
                    8: 90
                }
                if orientation in rotate_values:
                    img = img.rotate(rotate_values[orientation], expand=True)
    except (AttributeError, KeyError, IndexError):
        # No EXIF data or no orientation info
        pass

    img.thumbnail((1000, 1000))

    img_io = io.BytesIO()
    format = "JPEG"
    img.save(img_io, format=format, quality=85)
    return ContentFile(img_io.getvalue(), name=image.name.split('/')[-1])


class Entsendeform(OrgModel):
    name = models.CharField(max_length=50, verbose_name='Entsendeform-Name')

    class Meta:
        verbose_name = 'Entsendeform'
        verbose_name_plural = 'Entsendeformen'

    def __str__(self):
        return self.name


class Kirchenzugehoerigkeit(OrgModel):
    name = models.CharField(max_length=50, verbose_name='Kirchenzugehoerigkeit-Name')

    class Meta:
        verbose_name = 'Kirchenzugehörigkeit'
        verbose_name_plural = 'Kirchenzugehörigkeiten'

    def __str__(self):
        return self.name


class Einsatzland(OrgModel):
    name = models.CharField(max_length=50, verbose_name='Einsatzland')
    code = models.CharField(max_length=2, verbose_name='Einsatzland-Code')

    notfallnummern = models.TextField(verbose_name='Notfallnummern', null=True, blank=True)
    arztpraxen = models.TextField(verbose_name='Arztpraxen', null=True, blank=True)
    apotheken = models.TextField(verbose_name='Apotheken', null=True, blank=True)
    informationen = models.TextField(verbose_name='Weitere Informationen', null=True, blank=True)


    class Meta:
        verbose_name = 'Einsatzland'
        verbose_name_plural = 'Einsatzländer'

    def __str__(self):
        return self.name


class Einsatzstelle(OrgModel):
    name = models.CharField(max_length=50, verbose_name='Einsatzstelle')
    land = models.ForeignKey(Einsatzland, on_delete=models.CASCADE, verbose_name='Einsatzland', null=True, blank=True)

    partnerorganisation = models.TextField(verbose_name='Partnerorganisation', null=True, blank=True)
    arbeitsvorgesetzter = models.TextField(verbose_name='Arbeitsvorgesetzte:r', null=True, blank=True)
    mentor = models.TextField(verbose_name='Mentor:in', null=True, blank=True)
    botschaft = models.TextField(verbose_name='Botschaft', null=True, blank=True)
    konsulat = models.TextField(verbose_name='Konsulat', null=True, blank=True)
    informationen = models.TextField(verbose_name='Weitere Informationen', null=True, blank=True)

    class Meta:
        verbose_name = 'Einsatzstelle'
        verbose_name_plural = 'Einsatzstellen'

    def __str__(self):
        return self.name


class Jahrgang(OrgModel):
    name = models.CharField(max_length=50, verbose_name='Jahrgang')
    start = models.DateField(verbose_name='Startdatum')
    ende = models.DateField(verbose_name='Enddatum')
    typ = models.ForeignKey(JahrgangTyp, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='Typ')

    class Meta:
        verbose_name = 'Jahrgang'
        verbose_name_plural = 'Jahrgänge'

    def __str__(self):
        return self.name
    
    def get_queryset(self):
        if self.request.user.org == self.org:
            return super().get_queryset()
        else:
            return super().get_queryset().filter(org=self.request.user.org)


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
    user = models.OneToOneField(User, on_delete=models.DO_NOTHING, null=True, blank=True, verbose_name='Benutzer:in')
    first_name = models.CharField(max_length=50, verbose_name='Vorname')
    last_name = models.CharField(max_length=50, verbose_name='Nachname')
    geschlecht = models.CharField(max_length=1, blank=True, null=True, choices=GESCHLECHT_CHOICES, verbose_name='Geschlecht')
    geburtsdatum = models.DateField(blank=True, null=True, verbose_name='Geburtsdatum')
    strasse = models.CharField(max_length=100, blank=True, null=True, verbose_name='Straße')
    plz = models.CharField(max_length=10, blank=True, null=True, verbose_name='PLZ')
    ort = models.CharField(max_length=100, blank=True, null=True, verbose_name='Ort')
    country = models.CharField(max_length=100, blank=True, null=True, verbose_name='Land', default='Deutschland')
    email = models.EmailField(max_length=100, verbose_name='E-Mail')
    phone = models.CharField(max_length=20, blank=True, null=True, verbose_name='Telefon')
    phone_einsatzland = models.CharField(max_length=20, blank=True, null=True, verbose_name='Telefon Einsatzland')
    entsendeform = models.ForeignKey(Entsendeform, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='Entsendeform')
    einsatzland = models.ForeignKey(Einsatzland, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='Einsatzland')
    einsatzstelle = models.ForeignKey(Einsatzstelle, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='Einsatzstelle')
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
    
    def send_register_email(self):
        from FW.tasks import send_register_email_task
        send_register_email_task.delay(self)

    def __str__(self):
        return self.first_name + ' ' + self.last_name


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
        if instance.has_field_changed('ende_real'):
            tasks = FreiwilligerAufgaben.objects.filter(freiwilliger=instance, faellig__isnull=False,
                                                        aufgabe__faellig_tage_vor_ende__isnull=False, erledigt=False, pending=False)
            start_date = instance.start_real or instance.start_geplant or instance.jahrgang.start
            for task in tasks:
                task.faellig = start_date - timedelta(days=task.aufgabe.faellig_tage_vor_ende)
                task.save()
        if instance.has_field_changed('start_real'):
            tasks = FreiwilligerAufgaben.objects.filter(freiwilliger=instance, faellig__isnull=False,
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


class Notfallkontakt(OrgModel):
    first_name = models.CharField(max_length=50, verbose_name='Vorname')
    last_name = models.CharField(max_length=50, verbose_name='Nachname')
    phone_work = models.CharField(max_length=20, blank=True, null=True, verbose_name='Telefon (Arbeit)')
    phone = models.CharField(max_length=20, blank=True, null=True, verbose_name='Telefon (Mobil)')
    email = models.EmailField(max_length=100, blank=True, null=True, verbose_name='E-Mail')
    freiwilliger = models.ForeignKey(Freiwilliger, on_delete=models.CASCADE, verbose_name='Freiwillige:r', null=True, blank=True)

    class Meta:
        verbose_name = 'Notfallkontakt'
        verbose_name_plural = 'Notfallkontakte'

    def __str__(self):
        return self.first_name + ' ' + self.last_name


class Ampel(OrgModel):
    CHOICES = [
        ('G', 'Grün'),
        ('Y', 'Gelb'),
        ('R', 'Rot'),
    ]

    freiwilliger = models.ForeignKey(Freiwilliger, on_delete=models.CASCADE, verbose_name='Freiwillige:r')
    status = models.CharField(max_length=1, choices=CHOICES, verbose_name='Ampelmeldung')
    comment = models.TextField(blank=True, null=True, verbose_name='Kommentar')
    date = models.DateTimeField(auto_now_add=True, verbose_name='Datum')

    class Meta:
        verbose_name = 'Ampel'
        verbose_name_plural = 'Ampeln'

    def __str__(self):
        return self.freiwilliger.first_name + ' ' + self.freiwilliger.last_name + ' - ' + self.status


class Aufgabenprofil(OrgModel):
    name = models.CharField(max_length=50, verbose_name='Aufgabenprofil-Name')
    beschreibung = models.TextField(null=True, blank=True, verbose_name='Beschreibung')
    einsatzland = models.ForeignKey(Einsatzland, on_delete=models.CASCADE, null=True, blank=True, verbose_name='Einsatzland')
    einsatzstelle = models.ForeignKey(Einsatzstelle, on_delete=models.CASCADE, null=True, blank=True, verbose_name='Einsatzstelle')
    aufgaben = models.ManyToManyField('Aufgabe', blank=True, verbose_name='Aufgaben')

    class Meta:
        verbose_name = 'Aufgabenprofil'
        verbose_name_plural = 'Aufgabenprofil'

    def __str__(self):
        return self.name


class FreiwilligerAufgaben(OrgModel):
    WIEDERHOLUNG_CHOICES = [
        ('T', 'Täglich'),
        ('W', 'Wöchentlich'),
        ('M', 'Monatlich'),
        ('J', 'Jährlich'),
        ('N', 'Nicht wiederholen')
    ]

    freiwilliger = models.ForeignKey(Freiwilliger, on_delete=models.CASCADE, verbose_name='Freiwillige:r')
    aufgabe = models.ForeignKey('Aufgabe', on_delete=models.CASCADE, verbose_name='Aufgabe')
    personalised_description = models.TextField(blank=True, null=True, verbose_name='Persönliche Beschreibung')
    erledigt = models.BooleanField(default=False, verbose_name='Erledigt')
    pending = models.BooleanField(default=False, verbose_name='Wird bearbeitet')
    datetime = models.DateTimeField(auto_now_add=True, verbose_name='Erstellt am')
    faellig = models.DateField(blank=True, null=True, verbose_name='Fällig am')
    last_reminder = models.DateField(blank=True, null=True, verbose_name='Letzte Erinnerung')
    erledigt_am = models.DateField(blank=True, null=True, verbose_name='Erledigt am')
    wiederholung = models.CharField(max_length=1, choices=WIEDERHOLUNG_CHOICES, default='N', verbose_name='Wiederholung')
    wiederholung_ende = models.DateField(blank=True, null=True, verbose_name='Wiederholung bis')
    file = models.FileField(upload_to='uploads/', blank=True, null=True, verbose_name='Datei')

    def save(self, *args, **kwargs):
        if self.wiederholung != 'N' and not self.wiederholung_ende:
            self.wiederholung_ende = self.freiwilliger.ende_geplant
        if not self.faellig:

            if self.aufgabe.faellig_tage_nach_start:
                self.faellig = (self.freiwilliger.start_geplant or self.freiwilliger.jahrgang.start) + timedelta(days=self.aufgabe.faellig_tage_nach_start)
            elif self.aufgabe.faellig_tage_vor_ende:
                self.faellig = (self.freiwilliger.ende_geplant or self.freiwilliger.jahrgang.ende) - timedelta(days=self.aufgabe.faellig_tage_vor_ende)
            elif self.aufgabe.faellig_monat:
                # self.faellig = self.aufgabe.faellig
                month = self.aufgabe.faellig_monat or 1
                day = self.aufgabe.faellig_tag or 1

                try:
                    if self.aufgabe.faellig_art == 'V':
                        start_date = self.freiwilliger.start_real or self.freiwilliger.start_geplant or self.freiwilliger.jahrgang.start
                        year = start_date.year
                        if start_date.month < month or (start_date.month == month and start_date.day <= day):
                            year -= 1
                    elif self.aufgabe.faellig_art == 'W':
                        start_date = self.freiwilliger.start_real or self.freiwilliger.start_geplant or self.freiwilliger.jahrgang.start
                        year = start_date.year
                        if start_date.month > month or (start_date.month == month and start_date.day >= day):
                            year = (self.freiwilliger.ende_geplant or self.freiwilliger.jahrgang.ende).year
                    elif self.aufgabe.faellig_art == 'N':
                        end_date = self.freiwilliger.ende_geplant or self.freiwilliger.jahrgang.ende
                        year = end_date.year
                        if end_date.month > month or (end_date.month == month and end_date.day >= day):
                            year += 1
                    elif self.aufgabe.faellig_art == 'A':
                        year = datetime.now().year
                        if datetime.now().month > month or (datetime.now().month == month and datetime.now().day >= day):
                            year -= 1
                    
                    self.faellig = datetime(year, month, day).date()

                except Exception as e:
                    print(e)
                    pass
        
        super(FreiwilligerAufgaben, self).save(*args, **kwargs)


    def send_reminder_email(self):
        from Global.send_email import send_aufgaben_email
        send_aufgaben_email(self)


    class Meta:
        verbose_name = 'Freiwillige:r Aufgabe'
        verbose_name_plural = 'Freiwillige:r Aufgaben'

    def __str__(self):
        return self.freiwilliger.first_name + ' ' + self.freiwilliger.last_name + ' - ' + self.aufgabe.name


class FreiwilligerUpload(OrgModel):
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

class FreiwilligerFotos(OrgModel):
    freiwilliger = models.ForeignKey(Freiwilliger, on_delete=models.CASCADE, verbose_name='Freiwillige:r')
    file = models.ImageField(upload_to='fotos/', verbose_name='Foto')
    datetime = models.DateTimeField(auto_now_add=True, verbose_name='Erstellt am')

    class Meta:
        verbose_name = 'Freiwilliger Foto'
        verbose_name_plural = 'Freiwilliger Fotos'

    def __str__(self):
        return self.file.name


class FreiwilligerAufgabenprofil(OrgModel):
    freiwilliger = models.ForeignKey(Freiwilliger, on_delete=models.CASCADE, verbose_name='Freiwillige:r')
    aufgabenprofil = models.ForeignKey(Aufgabenprofil, on_delete=models.CASCADE, verbose_name='Aufgabenprofil')

    class Meta:
        verbose_name = 'Freiwilliger Aufgabenprofil'
        verbose_name_plural = 'Freiwilliger Aufgabenprofil'

    def __str__(self):
        return self.freiwilliger.first_name + ' ' + self.freiwilliger.last_name + ' - ' + self.aufgabenprofil.name


@receiver(post_save, sender=FreiwilligerAufgabenprofil)
def post_save_handler(sender, instance, **kwargs):
    aufgaben = instance.aufgabenprofil.aufgaben.all()
    for aufgabe in aufgaben:
        aufg, created = FreiwilligerAufgaben.objects.get_or_create(org=instance.org, freiwilliger=instance.freiwilliger, aufgabe=aufgabe)
        if not aufg.faellig:
            if aufgabe.faellig_tage_nach_start:
                aufg.faellig = instance.freiwilliger.start_geplant + timedelta(days=aufgabe.faellig_tage_nach_start)
            elif aufgabe.faellig_tage_vor_ende:
                aufg.faellig = instance.freiwilliger.ende_geplant - timedelta(days=aufgabe.faellig_tage_vor_ende)
            else:
                aufg.faellig = aufgabe.faellig
            aufg.save()

@receiver(pre_delete, sender=FreiwilligerAufgabenprofil)
def post_delete_handler(sender, instance, **kwargs):
    aufgaben = AufgabenprofilAufgabe.objects.filter(aufgabenprofil=instance.aufgabenprofil)
    for aufgabe in aufgaben:
        FreiwilligerAufgaben.objects.filter(freiwilliger=instance.freiwilliger, aufgabe=aufgabe.aufgabe).delete()


class Aufgabe(OrgModel):
    FAELLIG_CHOICES = [
        ('V', 'Vor Einsatzstart'),
        ('W', 'Während Einsatz'),
        ('N', 'Nach Einsatzende'),
        ('A', 'Aktuelles Jahr'),
    ]
    
    name = models.CharField(max_length=50, verbose_name='Aufgabenname')
    beschreibung = models.TextField(null=True, blank=True, verbose_name='Beschreibung')
    mitupload = models.BooleanField(default=True, verbose_name='Upload möglich')
    requires_submission = models.BooleanField(default=True, verbose_name='Bestätigung erforderlich')
    faellig_art = models.CharField(max_length=1, choices=FAELLIG_CHOICES, default='W', verbose_name='Fällig Art')
    faellig_tag = models.IntegerField(blank=True, null=True, verbose_name='Fällig Tag')
    faellig_monat = models.IntegerField(blank=True, null=True, verbose_name='Fällig Monat')
    faellig_tage_nach_start = models.IntegerField(blank=True, null=True, verbose_name='Fällig Tage nach Einsatzstart')
    faellig_tage_vor_ende = models.IntegerField(blank=True, null=True, verbose_name='Fällig Tage vor Einsatzende')

    class Meta:
        verbose_name = 'Aufgabe'
        verbose_name_plural = 'Aufgaben'

    def __str__(self):
        return self.name


class Post(OrgModel):
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


class Bilder(OrgModel):
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


class BilderGallery(OrgModel):
    image = models.ImageField(upload_to='bilder/', verbose_name='Bild')

    small_image = models.ImageField(upload_to='bilder/small/', blank=True, null=True, verbose_name='Kleines Bild')
    bilder = models.ForeignKey(Bilder, on_delete=models.CASCADE, verbose_name='Bild')

    class Meta:
        verbose_name = 'Bilder Gallery'
        verbose_name_plural = 'Bilder Galleries'

    def __str__(self):
        return self.image.name


@receiver(post_save, sender=BilderGallery)
def create_small_image(sender, instance, created, **kwargs):
    """Create small version of uploaded image on save."""
    print(instance.image.name)
    if created and instance.image and not instance.small_image:
        try:
            # Open the image
            img = Image.open(instance.image)
            
            # Check for EXIF orientation and rotate if needed
            try:
                exif = img._getexif()
                if exif:
                    orientation = exif.get(274)  # 274 is the orientation tag
                    if orientation:
                        rotate_values = {
                            3: 180,
                            6: 270,
                            8: 90
                        }
                        if orientation in rotate_values:
                            img = img.rotate(rotate_values[orientation], expand=True)
            except (AttributeError, KeyError, IndexError):
                # No EXIF data or no orientation info
                pass

            # Create thumbnail
            img.thumbnail((1000, 1000))

            # Save to buffer
            img_io = io.BytesIO()
            format = "JPEG"  # Always save as JPEG for consistency
            img.save(img_io, format=format, quality=85)
            
            # Create filename
            extension = format.lower()

            filename = f"{os.path.basename(instance.image.name).rsplit('.', 1)[0]}.{extension}"

            print(filename)
            print('--------------------------------')
            
            # Save small image
            instance.small_image = ContentFile(img_io.getvalue(), name=filename)
            instance.save()

            print(instance.small_image.path)
            print('--------------------------------')
            
        except Exception as e:
            print(f"Error creating small image: {str(e)}")

@receiver(pre_delete, sender=BilderGallery)
def delete_bilder_files(sender, instance, **kwargs):
    """Delete image files when BilderGallery instance is deleted."""
    try:
        # Delete main image file if it exists
        if instance.image:
            if os.path.isfile(instance.image.path):
                os.remove(instance.image.path)
        
        # Delete small image file if it exists
        if instance.small_image:
            if os.path.isfile(instance.small_image.path):
                os.remove(instance.small_image.path)
    except Exception as e:
        print(f"Error deleting image files: {str(e)}")



class ProfilUser(OrgModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='Benutzer')
    attribut = models.CharField(max_length=50, verbose_name='Attribut')
    value = models.TextField(verbose_name='Wert')

    class Meta:
        verbose_name = 'Profil User'
        verbose_name_plural = 'Profil User'

    def __str__(self):
        return self.user + self.attribut
