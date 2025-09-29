from django.db import models
from Global.models import OrgModel
from django.contrib.auth.models import User
from Global.models import Einsatzland2, Einsatzstelle2


# Create your models here.
class Bewerber(OrgModel):
    # Status choices for applicant evaluation
    # Red = Critical issues, Yellow = Minor concerns, Green = No issues
    STATUS_CHOICES = [
        ("red", "Rot"),
        ("yellow", "Gelb"),
        ("green", "Grün"),
    ]
    
    # Evaluation options for applicant assessment
    # G = Suitable, B = Conditionally suitable, N = Not suitable
    bewertungsmoeglicheiten = (
        ("G", "Geeignet"),
        ("B", "Bedingt geeignet"),
        ("N", "Nicht geeignet"),
    )

    # Core user relationship and verification fields
    # Links the applicant to their user account and stores verification token for email verification
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, verbose_name="Benutzer:in"
    )
    verification_token = models.CharField(
        verbose_name="Verifikationstoken", max_length=255, null=True, blank=True
    )
    
    # Fields to track completion status of the application process
    abgeschlossen = models.BooleanField(verbose_name="Abgeschlossen", default=False)
    abgeschlossen_am = models.DateTimeField(
        verbose_name="Abgeschlossen am", null=True, blank=True
    )
    
    # Status and access control fields for applicant management
    status = models.CharField(
        verbose_name="Status",
        max_length=20,
        choices=STATUS_CHOICES,
        null=True,
        blank=True,
    )
    status_comment = models.TextField(
        verbose_name="Statuskommentar",
        null=True,
        blank=True,
        help_text="Der Kommentar, der dem Status zugeordnet wird.",
    )
    accessible_by_team_member = models.ManyToManyField(
        User,
        verbose_name="Zugriff auf Bewerbung",
        blank=True,
        help_text="Die Teammitglieder/Ehemaligen, die auf die Bewerbung des Bewerbers:in zugreifen können.",
        related_name="accessible_applications",
    )
    
    gegenstand = models.CharField(
        max_length=200, blank=True, null=True, verbose_name="Gegenstand"
    )
    
    # Wish preferences for deployment locations - applicants can specify up to 3 preferred locations
    # and one location they definitely don't want to be assigned to
    first_wish = models.CharField(
        max_length=200, blank=True, null=True, verbose_name="Erstwunsch"
    )
    first_wish_einsatzland = models.ForeignKey(
        Einsatzland2,
        on_delete=models.SET_NULL,
        related_name="first_wish_einsatzland",
        blank=True,
        null=True,
        verbose_name="Erstwunsch Einsatzland",
    )
    first_wish_einsatzstelle = models.ForeignKey(
        Einsatzstelle2,
        on_delete=models.SET_NULL,
        related_name="first_wish_einsatzstelle",
        blank=True,
        null=True,
        verbose_name="Erstwunsch Einsatzstelle",
    )
    second_wish = models.CharField(
        max_length=200, blank=True, null=True, verbose_name="Zweitwunsch"
    )
    second_wish_einsatzland = models.ForeignKey(
        Einsatzland2,
        on_delete=models.DO_NOTHING,
        related_name="second_wish_einsatzland",
        blank=True,
        null=True,
        verbose_name="Zweitwunsch Einsatzland",
    )
    second_wish_einsatzstelle = models.ForeignKey(
        Einsatzstelle2,
        on_delete=models.SET_NULL,
        related_name="second_wish_einsatzstelle",
        blank=True,
        null=True,
        verbose_name="Zweitwunsch Einsatzstelle",
    )
    third_wish = models.CharField(
        max_length=200, blank=True, null=True, verbose_name="Drittwunsch"
    )
    third_wish_einsatzland = models.ForeignKey(
        Einsatzland2,
        on_delete=models.SET_NULL,
        related_name="third_wish_einsatzland",
        blank=True,
        null=True,
        verbose_name="Drittwunsch Einsatzland",
    )
    third_wish_einsatzstelle = models.ForeignKey(
        Einsatzstelle2,
        on_delete=models.SET_NULL,
        related_name="third_wish_einsatzstelle",
        blank=True,
        null=True,
        verbose_name="Drittwunsch Einsatzstelle",
    )
    no_wish = models.CharField(
        max_length=200, blank=True, null=True, verbose_name="Nicht"
    )
    no_wish_einsatzland = models.ForeignKey(
        Einsatzland2,
        on_delete=models.SET_NULL,
        related_name="no_wish_einsatzland",
        blank=True,
        null=True,
        verbose_name="Nicht Einsatzland",
    )
    no_wish_einsatzstelle = models.ForeignKey(
        Einsatzstelle2,
        on_delete=models.SET_NULL,
        related_name="no_wish_einsatzstelle",
        blank=True,
        null=True,
        verbose_name="Nicht Einsatzstelle",
    )

    # Assignment and evaluation fields for tracking final placement and assessment
    zuteilung = models.ForeignKey(
        Einsatzstelle2,
        on_delete=models.SET_NULL,
        related_name="zuteilung",
        blank=True,
        null=True,
        verbose_name="Zuteilung",
    )
    endbewertung = models.CharField(
        max_length=1,
        choices=bewertungsmoeglicheiten,
        blank=True,
        null=True,
        verbose_name="Endbewertung",
    )
    note = models.FloatField(blank=True, null=True, verbose_name="Note")
    kommentar_zusammenfassung = models.TextField(
        blank=True, null=True,
        verbose_name="Zusammenfassung der Kommentare"
    )

    # Interview fields for tracking who conducted the interviews
    interview_1 = models.ForeignKey(
        User,
        on_delete=models.DO_NOTHING,
        related_name="interview_1",
        blank=True,
        null=True,
        verbose_name="Interviewperson 1",
    )
    interview_2 = models.ForeignKey(
        User,
        on_delete=models.DO_NOTHING,
        related_name="interview_2",
        blank=True,
        null=True,
        verbose_name="Interviewperson 2",
    )

    def __str__(self):
        return self.user.first_name + " " + self.user.last_name

    class Meta:
        ordering = ["user__first_name", "user__last_name"]
        verbose_name = "Bewerber:in"
        verbose_name_plural = "Bewerber:innen"


class ApplicationQuestion(OrgModel):
    ANSWER_TYPE_CHOICES = [
        ("t", "Text"),
        ("f", "Datei"),
    ]
    question = models.TextField(
        verbose_name="Frage",
        help_text="Die Frage, die der Bewerber:in beantworten soll.",
    )
    choices = models.TextField(
        verbose_name="Auswahlmöglichkeiten",
        null=True,
        blank=True,
        help_text="Kommagetrennte Liste von Auswahlmöglichkeiten, die der Bewerber:in auswählen kann. Wenn leer, wird die Antwort als Textfeld angezeigt.",
    )
    description = models.TextField(
        verbose_name="Beschreibung",
        null=True,
        blank=True,
        help_text="Die Beschreibung der Frage, die der Bewerber:in beantworten soll.",
    )
    order = models.IntegerField(
        verbose_name="Position",
        null=True,
        blank=True,
        help_text="Die Position der Frage in der Bewerbung. Wenn leer, wird hinten eingefügt.",
    )
    max_length = models.IntegerField(
        verbose_name="Maximale Länge",
        default=1000,
        null=True,
        blank=True,
        help_text="Die maximale Länge der Antwort.",
    )

    def __str__(self):
        return self.question

    def save(self, *args, **kwargs):
        if not self.order:
            max_order = (
                ApplicationQuestion.objects.filter(org=self.org).aggregate(
                    models.Max("order")
                )["order__max"]
                or 0
            )
            self.order = max_order + 1

        questions_same_order = ApplicationQuestion.objects.filter(
            org=self.org, order=self.order
        ).exclude(id=self.id)
        if questions_same_order.exists():
            for question in questions_same_order:
                question.order = question.order + 1
                question.save()

        super().save(*args, **kwargs)

    class Meta:
        ordering = ["order"]
        unique_together = ("org", "order")
        verbose_name = "Bewerbungsfrage"
        verbose_name_plural = "Bewerbungsfragen"


class ApplicationAnswer(OrgModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="Benutzer:in")
    question = models.ForeignKey(
        ApplicationQuestion,
        on_delete=models.CASCADE,
        verbose_name="Frage",
        help_text="Die Frage, die der Bewerber:in beantworten soll.",
    )
    answer = models.TextField(
        verbose_name="Antwort",
        null=True,
        blank=True,
        help_text="Die Antwort, die der Bewerber:in gegeben hat.",
    )

    def __str__(self):
        return self.answer

    class Meta:
        verbose_name = "Bewerbungsantwort"
        verbose_name_plural = "Bewerbungsantworten"


class ApplicationText(OrgModel):
    welcome = models.TextField(
        verbose_name="Begrüßung",
        help_text="Die Begrüßung, die der Bewerber:in beim Start der Bewerbung sieht.",
    )
    footer = models.TextField(
        verbose_name="Fußzeile",
        help_text="Die Fußzeile, die der Bewerber:in am Ende der Bewerbung sieht.",
    )
    deadline = models.DateField(
        verbose_name="Abgabefrist",
        null=True,
        blank=True,
        help_text="Die Abgabefrist, bis zu welcher die Bewerbung abgeschlossen werden muss.",
    )
    welcome_account_create = models.TextField(
        verbose_name="Begrüßung bei Kontoerstellung",
        help_text="Die Begrüßung, die der Bewerber:in beim Erstellen des Kontos sieht.",
        null=True,
        blank=True,
    )

    def __str__(self):
        return self.org.name

    class Meta:
        verbose_name = "Bewerbungstext"
        verbose_name_plural = "Bewerbungstexte"


class ApplicationFileQuestion(OrgModel):
    ALLOWED_EXTENSIONS = [".pdf", ".doc", ".docx", ".txt", ".png", ".jpg", ".jpeg"]

    name = models.CharField(
        verbose_name="Name",
        max_length=255,
        help_text="Der Name der Datei, die der Bewerber:in hochladen muss.",
    )
    description = models.TextField(
        verbose_name="Beschreibung",
        null=True,
        blank=True,
        help_text="Die Beschreibung der Datei, die der Bewerber:in hochladen muss.",
    )
    order = models.IntegerField(
        verbose_name="Position",
        null=True,
        blank=True,
        help_text="Die Position der Datei in der Bewerbung. Wenn leer, wird hinten eingefügt.",
    )
    is_profile_picture = models.BooleanField(
        verbose_name="Ist Profilbild",
        default=False,
        help_text="Dieses Bild wird als Profilbild des Bewerbers:in angezeigt.",
    )

    def save(self, *args, **kwargs):
        if not self.order:
            max_order = (
                ApplicationFileQuestion.objects.filter(org=self.org).aggregate(
                    models.Max("order")
                )["order__max"]
                or 0
            )
            self.order = max_order + 1
        super().save(*args, **kwargs)

    def __str__(self):
        return self.org.name

    class Meta:
        ordering = ["order"]
        verbose_name = "Bewerbungsdatei"
        verbose_name_plural = "Bewerbungsdateien"


class ApplicationAnswerFile(OrgModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="Benutzer:in")
    file_question = models.ForeignKey(
        ApplicationFileQuestion, on_delete=models.CASCADE, verbose_name="Datei"
    )
    file = models.FileField(
        verbose_name="Datei", upload_to="bewerbung/", null=True, blank=True
    )
    
    def save(self, *args, **kwargs):
        if self.file_question.is_profile_picture:
            try:
                self.user.customuser.profil_picture = self.file
                self.user.customuser.save()
            except Exception as e:
                print(e)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.org.name

    class Meta:
        verbose_name = "Bewerbungsdatei"
        verbose_name_plural = "Bewerbungsdateien"
