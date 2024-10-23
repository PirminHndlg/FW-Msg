from django.contrib.auth.models import User
from django.db import models
from ORG.models import Organisation
from django.db.models.signals import post_save, post_delete
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

class CustomUser(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    org = models.ForeignKey(Organisation, on_delete=models.CASCADE)

    def __str__(self):
        return self.user.username


class Entsendeform(models.Model):
    org = models.ForeignKey(Organisation, on_delete=models.CASCADE)
    name = models.CharField(max_length=50)

    class Meta:
        verbose_name = 'Entsendeform'
        verbose_name_plural = 'Entsendeformen'

    def __str__(self):
        return self.name


class Notfallkontakt(models.Model):
    org = models.ForeignKey(Organisation, on_delete=models.CASCADE)
    first_name = models.CharField(max_length=50)
    last_name = models.CharField(max_length=50)
    phone = models.CharField(max_length=20)
    email = models.EmailField(max_length=100, blank=True, null=True)
    freiwilliger = models.ForeignKey('Freiwilliger', on_delete=models.CASCADE)

    class Meta:
        verbose_name = 'Notfallkontakt'
        verbose_name_plural = 'Notfallkontakte'

    def __str__(self):
        return self.first_name + ' ' + self.last_name


class Einsatzland(models.Model):
    org = models.ForeignKey(Organisation, on_delete=models.CASCADE)
    name = models.CharField(max_length=50)

    class Meta:
        verbose_name = 'Einsatzland'
        verbose_name_plural = 'Einsatzländer'

    def __str__(self):
        return self.name


class Einsatzstelle(models.Model):
    org = models.ForeignKey(Organisation, on_delete=models.CASCADE)
    name = models.CharField(max_length=50)
    land = models.ForeignKey(Einsatzland, on_delete=models.CASCADE)

    class Meta:
        verbose_name = 'Einsatzstelle'
        verbose_name_plural = 'Einsatzstellen'

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
    KONFESSION_CHOICES = [
        ('E', 'Evangelisch'),
        ('K', 'Katholisch'),
        ('A', 'Andere'),
        ('N', 'Keine Angabe')
    ]

    org = models.ForeignKey(Organisation, on_delete=models.CASCADE)
    user = models.OneToOneField(User, on_delete=models.DO_NOTHING)
    first_name = models.CharField(max_length=50)
    last_name = models.CharField(max_length=50)
    geschlecht = models.CharField(max_length=1, blank=True, null=True, choices=GESCHLECHT_CHOICES)
    geburtsdatum = models.DateField(blank=True, null=True)
    strasse = models.CharField(max_length=100, blank=True, null=True)
    plz = models.CharField(max_length=10, blank=True, null=True)
    ort = models.CharField(max_length=100, blank=True, null=True)
    email = models.EmailField(max_length=100, blank=True, null=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    phone_einsatzland = models.CharField(max_length=20, blank=True, null=True)
    entsendeform = models.ForeignKey(Entsendeform, on_delete=models.SET_NULL, null=True, blank=True)
    ekbo_anhalt = models.BooleanField(default=False)
    start_geplant = models.DateField(blank=True, null=True)
    start_real = models.DateField(blank=True, null=True)
    ende_geplant = models.DateField(blank=True, null=True)
    ende_real = models.DateField(blank=True, null=True)

    class Meta:
        verbose_name = 'Freiwillige:r'
        verbose_name_plural = 'Freiwillige'

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


@receiver(post_delete, sender=Freiwilliger)
def post_delete_handler(sender, instance, **kwargs):
    instance.user.delete()


class Aufgabenprofil(models.Model):
    org = models.ForeignKey(Organisation, on_delete=models.CASCADE)
    name = models.CharField(max_length=50)
    beschreibung = models.TextField(null=True, blank=True)
    einsatzland = models.ForeignKey(Einsatzland, on_delete=models.CASCADE, null=True, blank=True)
    einsatzstelle = models.ForeignKey(Einsatzstelle, on_delete=models.CASCADE, null=True, blank=True)

    class Meta:
        verbose_name = 'Aufgabenprofil'
        verbose_name_plural = 'Aufgabenprofile'

    def __str__(self):
        return self.name


class FreiwilligerAufgabenprofil(models.Model):
    # org = models.ForeignKey(Organisation, on_delete=models.CASCADE)
    freiwilliger = models.ForeignKey(Freiwilliger, on_delete=models.CASCADE)
    aufgabenprofil = models.ForeignKey(Aufgabenprofil, on_delete=models.CASCADE)

    class Meta:
        verbose_name = 'Freiwilliger Aufgabenprofil'
        verbose_name_plural = 'Freiwilliger Aufgabenprofile'

    def __str__(self):
        return self.freiwilliger.first_name + ' ' + self.freiwilliger.last_name + ' - ' + self.aufgabenprofil.name


class Aufgabe(models.Model):
    org = models.ForeignKey(Organisation, on_delete=models.CASCADE)
    name = models.CharField(max_length=50)
    beschreibung = models.TextField(null=True, blank=True)

    class Meta:
        verbose_name = 'Aufgabe'
        verbose_name_plural = 'Aufgaben'

    def __str__(self):
        return self.name


class AufgabenprofilAufgabe(models.Model):
    # org = models.ForeignKey(Organisation, on_delete=models.CASCADE)
    aufgabenprofil = models.ForeignKey(Aufgabenprofil, on_delete=models.CASCADE)
    aufgabe = models.ForeignKey(Aufgabe, on_delete=models.CASCADE)

    class Meta:
        verbose_name = 'Aufgabenprofil Aufgabe'
        verbose_name_plural = 'Aufgabenprofil Aufgaben'

    def __str__(self):
        return self.aufgabenprofil.name + ' - ' + self.aufgabe.name


class Post(models.Model):
    org = models.ForeignKey(Organisation, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    title = models.CharField(max_length=50)
    text = models.TextField()
    date = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Post'
        verbose_name_plural = 'Posts'

    def __str__(self):
        return self.title


@receiver(post_save, sender=Post)
def post_save_handler(sender, instance, **kwargs):
    if instance.org:
        pass
