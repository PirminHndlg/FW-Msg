from datetime import datetime, timedelta
import random
from django.contrib import admin
from .models import Freiwilliger, Entsendeform, Einsatzland, Einsatzstelle, Notfallkontakt, Post, Aufgabe, \
    Aufgabenprofil, FreiwilligerAufgabenprofil, Ampel, FreiwilligerAufgaben, Jahrgang, \
    CustomUser, Bilder, BilderGallery
from simple_history.admin import SimpleHistoryAdmin


# Register your models here.
@admin.register(Freiwilliger)
class FreiwilligerAdmin(SimpleHistoryAdmin):
    search_fields = ['first_name', 'last_name']
    actions = ['send_register_email', 'give_user_name', 'anonymize_user']

    def send_register_email(self, request, queryset):
        for freiwilliger in queryset:
            from FW.tasks import send_register_email_task
            send_register_email_task.delay(freiwilliger.id)

    def give_user_name(self, request, queryset):
        for freiwilliger in queryset:
            freiwilliger.user.first_name = freiwilliger.first_name
            freiwilliger.user.last_name = freiwilliger.last_name
            freiwilliger.user.save()

    def anonymize_user(self, request, queryset):
        for freiwilliger in queryset:
            random_date_in_2007 = datetime(2007, 1, 1).date() + timedelta(days=random.randint(0, 365))
            # Replace umlauts in name parts
            first = freiwilliger.first_name.replace('ä','ae').replace('ö','oe').replace('ü','ue').replace('ß','ss')
            last = freiwilliger.last_name.replace('ä','ae').replace('ö','oe').replace('ü','ue').replace('ß','ss')
            freiwilliger.user.email = f'{first}.{last}@p0k.de'
            freiwilliger.email = f'{first}.{last}@p0k.de'
            freiwilliger.geburtsdatum = random_date_in_2007
            freiwilliger.phone = None
            freiwilliger.phone_einsatzland = None
            freiwilliger.strasse = None
            freiwilliger.plz = None
            freiwilliger.ort = None
            freiwilliger.country = None
            freiwilliger.save()
            freiwilliger.user.save()

@admin.register(Entsendeform)
class EntsendeformAdmin(admin.ModelAdmin):
    search_fields = ['name']


@admin.register(Einsatzland)
class EinsatzlandAdmin(admin.ModelAdmin):
    search_fields = ['name']


@admin.register(Einsatzstelle)
class EinsatzstelleAdmin(admin.ModelAdmin):
    search_fields = ['name']


@admin.register(Notfallkontakt)
class NotfallkontaktAdmin(admin.ModelAdmin):
    search_fields = ['first_name', 'last_name']
    actions = ['anonymize_user']

    def anonymize_user(self, request, queryset):
        for notfallkontakt in queryset:
            notfallkontakt.first_name = f'{notfallkontakt.first_name[0]} anonymisiert'
            notfallkontakt.last_name = f'{notfallkontakt.last_name[0]} anonymisiert'
            notfallkontakt.phone = None
            notfallkontakt.phone_work = None
            notfallkontakt.email = f'{notfallkontakt.first_name}.{notfallkontakt.last_name}@p0k.de'
            notfallkontakt.save()


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    search_fields = ['title']


@admin.register(Aufgabe)
class AufgabeAdmin(admin.ModelAdmin):
    search_fields = ['name']


@admin.register(Aufgabenprofil)
class AufgabenprofilAdmin(admin.ModelAdmin):
    search_fields = ['name']


@admin.register(FreiwilligerAufgabenprofil)
class FreiwilligerAufgabenprofilAdmin(admin.ModelAdmin):
    search_fields = ['freiwilliger__user__first_name', 'freiwilliger__user__last_name', 'aufgabenprofil__name']


@admin.register(Ampel)
class AmpelAdmin(admin.ModelAdmin):
    search_fields = ['status']

@admin.register(FreiwilligerAufgaben)
class FreiwilligerAufgabenAdmin(admin.ModelAdmin):
    search_fields = ['freiwilliger__user__first_name', 'freiwilliger__user__last_name', 'aufgabe__name'] 
    actions = ['send_aufgaben_email']

    def send_aufgaben_email(self, request, queryset):
        for freiwilliger_aufgabe in queryset:
            freiwilliger_aufgabe.send_reminder_email()
        msg = f"Erinnerungen wurden gesendet"
        self.message_user(request, msg)


@admin.register(Jahrgang)
class JahrgangAdmin(admin.ModelAdmin):
    search_fields = ['name']


@admin.register(Bilder)
class BilderAdmin(admin.ModelAdmin):
    search_fields = ['name']
    list_display = ('titel', 'user', 'date_created')

@admin.register(BilderGallery)
class BilderGalleryAdmin(admin.ModelAdmin):
    search_fields = ['bilder']