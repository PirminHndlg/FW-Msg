from datetime import datetime, timedelta
import random
from django.contrib import admin
from .models import Freiwilliger, Entsendeform, Einsatzland, Einsatzstelle, Notfallkontakt, Post, Aufgabe, \
    Aufgabenprofil, FreiwilligerAufgabenprofil, Ampel, FreiwilligerAufgaben, Jahrgang, \
    CustomUser, Bilder, BilderGallery, AufgabeZwischenschritte, FreiwilligerAufgabenZwischenschritte, ProfilUser
from simple_history.admin import SimpleHistoryAdmin
from ORG.models import JahrgangTyp


# Register your models here.
@admin.register(Freiwilliger)
class FreiwilligerAdmin(SimpleHistoryAdmin):
    search_fields = ['first_name', 'last_name']
    actions = ['send_register_email', 'give_user_name', 'anonymize_user', 'move_to_new']

    def move_to_new(self, request, queryset):
        from ORG.models import Organisation
        from Global.models import PersonCluster, UserAttribute, Einsatzland2, Einsatzstelle2

        person_cluster = PersonCluster.objects.get(name='Freiwilliger')
        org = Organisation.objects.get(name=queryset.first().org.name)

        def get_or_create_attribute(name):
            from Global.models import Attribute
            attribute, created = Attribute.objects.get_or_create(name=name, org=org)
            if created:
                attribute.person_cluster.set([person_cluster])
            return attribute
        
        attributes = [
            get_or_create_attribute('geburtsdatum'),
            get_or_create_attribute('geschlecht'),
            get_or_create_attribute('kirchenzugehoerigkeit'),
            get_or_create_attribute('strasse'),
            get_or_create_attribute('plz'),
            get_or_create_attribute('ort'),
            get_or_create_attribute('country'),
            get_or_create_attribute('phone'),
            get_or_create_attribute('phone_einsatzland'),
        ]

        for freiwilliger in queryset:
            freiwilliger.user.customuser.first_name = freiwilliger.first_name
            freiwilliger.user.customuser.last_name = freiwilliger.last_name
            freiwilliger.user.customuser.geburtsdatum = freiwilliger.geburtsdatum
            freiwilliger.user.customuser.person_cluster = person_cluster
            freiwilliger.user.customuser.save()

            if freiwilliger.einsatzland:
                freiwilliger.einsatzland2 = Einsatzland2.objects.get(name=freiwilliger.einsatzland.name)
                freiwilliger.save()

            if freiwilliger.einsatzstelle:
                freiwilliger.einsatzstelle2 = Einsatzstelle2.objects.get(name=freiwilliger.einsatzstelle.name)
                freiwilliger.save()

            for attribute in attributes:
                UserAttribute.objects.get_or_create(
                    org=org,
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
    actions = ['move_to_new']

    def move_to_new(self, request, queryset):
        from Global.models import Einsatzland2

        for einsatzland in queryset:
            einsatzland2, created = Einsatzland2.objects.get_or_create(
                org=einsatzland.org,
                name=einsatzland.name,
                code=einsatzland.code,
            )
            if created:
                einsatzland2.notfallnummern = einsatzland.notfallnummern
                einsatzland2.arztpraxen = einsatzland.arztpraxen
                einsatzland2.apotheken = einsatzland.apotheken
                einsatzland2.informationen = einsatzland.informationen
            einsatzland2.save()


@admin.register(Einsatzstelle)
class EinsatzstelleAdmin(admin.ModelAdmin):
    search_fields = ['name']
    actions = ['move_to_new']

    def move_to_new(self, request, queryset):
        from Global.models import Einsatzstelle2, Einsatzland2

        for einsatzstelle in queryset:
            einsatzstelle2, created = Einsatzstelle2.objects.get_or_create(
                org=einsatzstelle.org,
                name=einsatzstelle.name,
            )
            if created:
                land = Einsatzland2.objects.get(name=einsatzstelle.land.name)
                einsatzstelle2.land = land

                einsatzstelle2.partnerorganisation = einsatzstelle.partnerorganisation
                einsatzstelle2.arbeitsvorgesetzter = einsatzstelle.arbeitsvorgesetzter
                einsatzstelle2.mentor = einsatzstelle.mentor
                einsatzstelle2.botschaft = einsatzstelle.botschaft
                einsatzstelle2.konsulat = einsatzstelle.konsulat
                einsatzstelle2.informationen = einsatzstelle.informationen

            einsatzstelle2.save()



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
    actions = ['set_jahrgang_typ_incoming', 'set_jahrgang_typ_outgoing', 'move_to_new']

    def set_jahrgang_typ_incoming(self, request, queryset):
        for aufgabe in queryset:
            aufgabe.jahrgang_typ = JahrgangTyp.objects.get(name='Incoming')
            aufgabe.save()
    
    def set_jahrgang_typ_outgoing(self, request, queryset):
        for aufgabe in queryset:
            aufgabe.jahrgang_typ = JahrgangTyp.objects.get(name='Outgoing')
            aufgabe.save()

    def move_to_new(self, request, queryset):
        from Global.models import Aufgabe2, PersonCluster

        person_cluster = PersonCluster.objects.get(name='Freiwilliger')

        for aufgabe in queryset:
            aufgabe2, created = Aufgabe2.objects.get_or_create(
                org=aufgabe.org,
                name=aufgabe.name,
                beschreibung=aufgabe.beschreibung,
                mitupload=aufgabe.mitupload,
                requires_submission=aufgabe.requires_submission,
                faellig_tag=aufgabe.faellig_tag,
                faellig_monat=aufgabe.faellig_monat,
                faellig_tage_nach_start=aufgabe.faellig_tage_nach_start,
                faellig_tage_vor_ende=aufgabe.faellig_tage_vor_ende,
            )
            if created:
                aufgabe2.person_cluster.set([person_cluster])
            aufgabe2.save()


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
    actions = ['send_aufgaben_email', 'move_to_new']

    def send_aufgaben_email(self, request, queryset):
        for freiwilliger_aufgabe in queryset:
            freiwilliger_aufgabe.send_reminder_email()
        msg = f"Erinnerungen wurden gesendet"
        self.message_user(request, msg)

    def move_to_new(self, request, queryset):
        from Global.models import UserAufgaben, PersonCluster, Aufgabe2

        person_cluster = PersonCluster.objects.get(name='Freiwilliger')

        for freiwilliger_aufgabe in queryset:
            aufgabe = Aufgabe2.objects.get(name=freiwilliger_aufgabe.aufgabe.name)

            if freiwilliger_aufgabe.file:
                file = freiwilliger_aufgabe.file
            else:
                file = None

            freiwilliger_aufgabe2, created = UserAufgaben.objects.get_or_create(
                user=freiwilliger_aufgabe.freiwilliger.user,
                aufgabe=aufgabe,
                org=freiwilliger_aufgabe.org,
                personalised_description=freiwilliger_aufgabe.personalised_description,
                erledigt=freiwilliger_aufgabe.erledigt,
                pending=freiwilliger_aufgabe.pending,
                datetime=freiwilliger_aufgabe.datetime,
                faellig=freiwilliger_aufgabe.faellig,
                last_reminder=freiwilliger_aufgabe.last_reminder,
                erledigt_am=freiwilliger_aufgabe.erledigt_am,
                wiederholung=freiwilliger_aufgabe.wiederholung,
                wiederholung_ende=freiwilliger_aufgabe.wiederholung_ende,
                file=file,
                benachrichtigung_cc=freiwilliger_aufgabe.benachrichtigung_cc,
            )
            freiwilliger_aufgabe2.save()


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

@admin.register(ProfilUser)
class ProfilUserAdmin(admin.ModelAdmin):
    search_fields = ['user__first_name', 'user__last_name']
    actions = ['move_to_new']

    def move_to_new(self, request, queryset):
        from Global.models import ProfilUser2

        for profiluser in queryset:
            profiluser2, created = ProfilUser2.objects.get_or_create(
                user=profiluser.user,
                attribut=profiluser.attribut,
                value=profiluser.value,
            )
            profiluser2.save()
