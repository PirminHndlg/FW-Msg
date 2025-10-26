from django.db import models
from django.utils.timezone import localtime
from BW.models import Bewerber
from django.contrib.auth.models import User
from Global.models import OrgModel
from ORG.models import Organisation as Org


# Create your models here.
class Fragekategorie(OrgModel):
    name = models.CharField(
        max_length=200, blank=False, null=False, verbose_name="Name"
    )
    short_name = models.CharField(
        max_length=100, blank=True, null=True, verbose_name="Kurzname"
    )

    class Meta:
        verbose_name = "Fragekategorie"
        verbose_name_plural = "Fragekategorien"

    def __str__(self):
        return self.name


class Frage(OrgModel):
    text = models.CharField(
        max_length=200, blank=False, null=False, verbose_name="Frage"
    )
    explanation = models.TextField(
        verbose_name="Erklärung (Optional)", blank=True, null=True
    )
    kategorie = models.ForeignKey(
        Fragekategorie,
        on_delete=models.CASCADE,
        blank=False,
        null=False,
        verbose_name="Kategorie",
    )
    min = models.IntegerField(default=1)
    max = models.IntegerField(default=5)

    @classmethod
    def change_min(cls, min_value):
        cls.min = min_value

    @classmethod
    def change_max(cls, max_value):
        cls.max = max_value

    class Meta:
        verbose_name = "Frage"
        verbose_name_plural = "Fragen"

    def __str__(self):
        return self.text


class Einheit(OrgModel):
    name = models.CharField(max_length=200)
    short_name = models.CharField(
        max_length=100, blank=True, null=True, verbose_name="Kurzname"
    )

    class Meta:
        verbose_name = "Einheit"
        verbose_name_plural = "Einheiten"

    def __str__(self):
        return self.name


class Bewertung(OrgModel):
    bewerter = models.ForeignKey(
        User, on_delete=models.CASCADE, verbose_name="Teammitglied"
    )
    bewerber = models.ForeignKey(
        Bewerber, on_delete=models.CASCADE, verbose_name="Freiwillige:r"
    )
    frage = models.ForeignKey(Frage, on_delete=models.CASCADE, verbose_name="Frage")
    einheit = models.ForeignKey(
        Einheit, on_delete=models.CASCADE, verbose_name="Einheit"
    )
    bewertung = models.IntegerField(verbose_name="Bewertung", blank=False, null=False)
    last_modified = models.DateTimeField(
        auto_now=True, verbose_name="Zuletzt bearbeitet"
    )

    class Meta:
        verbose_name = "Bewertung"
        verbose_name_plural = "Bewertungen"

    def __str__(self):
        return (
            self.bewerter.first_name
            + " "
            + self.bewerter.last_name
            + " - "
            + self.bewerber.first_name
            + " "
            + self.bewerber.last_name
            + " - "
            + self.frage.text
        )


class Kommentar(OrgModel):
    bewerter = models.ForeignKey(
        User, on_delete=models.CASCADE, verbose_name="Teammitglied"
    )
    bewerber = models.ForeignKey(
        Bewerber, on_delete=models.CASCADE, verbose_name="Freiwillige:r"
    )
    einheit = models.ForeignKey(
        Einheit, on_delete=models.CASCADE, verbose_name="Einheit"
    )
    kategorie = models.ForeignKey(
        Fragekategorie,
        on_delete=models.DO_NOTHING,
        blank=True,
        null=True,
        verbose_name="Kategorie",
    )
    text = models.TextField(verbose_name="Text")
    last_modified = models.DateTimeField(
        verbose_name="Zuletzt bearbeitet", auto_now=True
    )
    show_at_presentation = models.BooleanField(
        default=True, verbose_name="Bei Präsentation zeigen"
    )
    show_name_at_presentation = models.BooleanField(
        default=True, verbose_name="Namen anzeigen"
    )

    class Meta:
        verbose_name = "Kommentar"
        verbose_name_plural = "Kommentare"

    def __str__(self):
        return (
            self.bewerter.first_name
            + " "
            + self.bewerter.last_name
            + " - "
            + self.bewerber.first_name
            + " "
            + self.bewerber.last_name
            + " - "
            + self.text
        )
        

class Seminar(models.Model):
    org = models.OneToOneField(Org, on_delete=models.CASCADE)
    name = models.CharField(max_length=200, verbose_name="Seminarname", help_text="Der Name des Seminars, der Bewerber:innen und Teammitglieder beim Start des Seminars sehen.")
    description = models.TextField(verbose_name="Seminar Beschreibung", help_text="Die Beschreibung des Seminars, die Bewerber:innen und Teammitglieder beim Start des Seminars sehen.")
    seminar_start = models.DateField(verbose_name="Seminar Start", null=True, blank=True, help_text="Die Startdatum des Seminars.")
    seminar_end = models.DateField(verbose_name="Seminar Ende", null=True, blank=True, help_text="Die Enddatum des Seminars.")
    deadline_start = models.DateTimeField(verbose_name="Länderwahl Start", null=True, blank=True, help_text="Die Startzeit des Seminars, ab welcher die Bewerber:innen für die Auswahl des Einsatzlandes beginnen können.")
    deadline_end = models.DateTimeField(verbose_name="Länderwahl Ende", null=True, blank=True, help_text="Die Endzeit des Seminars, bis zu welcher die Bewerber:innen für die Auswahl des Einsatzlandes ihre Auswahl treffen müssen.")
    verschwiegenheit_von_user = models.ManyToManyField(User, blank=True, verbose_name="Verschwiegenheit von User")

    class Meta:
        verbose_name = "Seminar"
        verbose_name_plural = "Seminare"

    def __str__(self):
        return self.name
    
    def get_deadline_start(self):
        return localtime(self.deadline_start)

    def get_deadline_end(self):
        return localtime(self.deadline_end)