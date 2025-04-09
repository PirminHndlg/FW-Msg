from datetime import datetime, timedelta
import random
from django.contrib import admin
from .models import Freiwilliger, Entsendeform, Einsatzland, Einsatzstelle, Notfallkontakt, Post, Aufgabe, \
    Aufgabenprofil, FreiwilligerAufgabenprofil, Ampel, FreiwilligerAufgaben, Jahrgang, \
    CustomUser, Bilder, BilderGallery, AufgabeZwischenschritte, FreiwilligerAufgabenZwischenschritte
from simple_history.admin import SimpleHistoryAdmin
from ORG.models import JahrgangTyp


# Register your models here.
@admin.register(Freiwilliger)
class FreiwilligerAdmin(SimpleHistoryAdmin):
    search_fields = ['first_name', 'last_name']
    actions = ['send_register_email', 'give_user_name', 'anonymize_user']

    def move_to_new(self, request, queryset):
        from Global.models import Organisation, PersonCluster, UserAttribute, Freiwilliger2

        person_cluster = PersonCluster.objects.get(name='Freiwilliger')
        org = Organisation.objects.get(name=queryset.first().org.name)

        def create_attributes(name):
            from Global.models import Attribute
            attribute, created = Attribute.objects.get_or_create(name=name, type='T', org=org, person_cluster=person_cluster)
            return attribute
        
        attributes = [
            create_attributes('geburtsdatum'),
            create_attributes('geschlecht'),
            create_attributes('kirchenzugehoerigkeit'),
            create_attributes('strasse'),
            create_attributes('plz'),
            create_attributes('ort'),
            create_attributes('country'),
            create_attributes('phone'),
            create_attributes('phone_einsatzland'),
        ]

        for freiwilliger in queryset:

            fw2, created = Freiwilliger2.objects.get_or_create(
                user=freiwilliger.user,
                org=org,
            )

            fw2.customuser.geburtsdatum = freiwilliger.geburtsdatum
            fw2.customuser.person_cluster = person_cluster
            fw2.customuser.save()

            for attribute in attributes:
                UserAttribute.objects.get_or_create(
                    user=freiwilliger.user,
                    attribute=attribute,
                    value=getattr(freiwilliger, attribute.name),
                )



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
    actions = ['set_jahrgang_typ_incoming', 'set_jahrgang_typ_outgoing']

    def set_jahrgang_typ_incoming(self, request, queryset):
        for aufgabe in queryset:
            aufgabe.jahrgang_typ = JahrgangTyp.objects.get(name='Incoming')
            aufgabe.save()
    
    def set_jahrgang_typ_outgoing(self, request, queryset):
        for aufgabe in queryset:
            aufgabe.jahrgang_typ = JahrgangTyp.objects.get(name='Outgoing')
            aufgabe.save()


@admin.register(AufgabeZwischenschritte)
class AufgabeZwischenschritteAdmin(admin.ModelAdmin):
    search_fields = ['name']


@admin.register(FreiwilligerAufgabenZwischenschritte)
class FreiwilligerAufgabenZwischenschritteAdmin(admin.ModelAdmin):
    search_fields = ['freiwilliger_aufgabe__freiwilliger__user__first_name', 'freiwilliger_aufgabe__freiwilliger__user__last_name', 'aufgabe_zwischenschritt__name']


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