from django.contrib import admin
from .models import Ordner, Dokument, Referenten, JahrgangTyp, DokumentColor
from simple_history.admin import SimpleHistoryAdmin

# Register your models here.

@admin.register(Ordner)
class OrdnerAdmin(SimpleHistoryAdmin):
    search_fields = ['ordner_name']
    actions = ['all_to_incoming', 'all_to_outgoing', 'move_to_new']

    def all_to_incoming(self, request, queryset):
        for ordner in queryset:
            ordner.typ = JahrgangTyp.objects.get(name='Incoming')
            ordner.save()
            
    def all_to_outgoing(self, request, queryset):
        for ordner in queryset:
            ordner.typ = JahrgangTyp.objects.get(name='Outgoing')
            ordner.save()

    def move_to_new(self, request, queryset):
        from Global.models import Ordner2, PersonCluster

        person_cluster = PersonCluster.objects.get(name='Freiwilliger')

        for ordner in queryset:
            ordner2, created = Ordner2.objects.get_or_create(
                org=ordner.org,
                ordner_name=ordner.ordner_name,
            )
            if created:
                ordner2.typ = set([ordner.typ])
                ordner2.save()
                

@admin.register(Dokument)
class DokumentAdmin(SimpleHistoryAdmin):
    search_fields = ['ordner', 'dokument', 'beschreibung']
    actions = ['move_to_new']

    def move_to_new(self, request, queryset):
        from Global.models import Dokument2

        for dokument in queryset:
            dokument2, created = Dokument2.objects.get_or_create(
                org=dokument.org,
                ordner=dokument.ordner,
                dokument=dokument.dokument,
                link=dokument.link,
                titel=dokument.titel,
                beschreibung=dokument.beschreibung,
                date_created=dokument.date_created,
                date_modified=dokument.date_modified,
                preview_image=dokument.preview_image,
            )
            dokument2.save()
        

@admin.register(DokumentColor)
class DokumentColorAdmin(SimpleHistoryAdmin):
    search_fields = ['name']

@admin.register(Referenten)
class ReferentenAdmin(SimpleHistoryAdmin):
    search_fields = ['first_name', 'last_name', 'email', 'phone']
    actions = ['anonymize_user', 'move_to_new']

    def anonymize_user(self, request, queryset):
        for referent in queryset:
            referent.email = f'{referent.first_name[0]}.{referent.last_name[0]}@p0k.de'
            referent.user.email = f'{referent.first_name[0]}.{referent.last_name[0]}@p0k.de'
            referent.phone_work = None
            referent.phone_mobil = None
            referent.save()
            referent.user.save()

    def move_to_new(self, request, queryset):
        from Global.models import Referenten2, Einsatzland2

        for referent in queryset:
            referent2, created = Referenten2.objects.get_or_create(
                org=referent.org,
                user=referent.user,
            )
            if created:
                land = referent.land.all()
                for l in land:
                    referent2.land.add(Einsatzland2.objects.get(name=l.name))
            referent2.save()

@admin.register(JahrgangTyp)
class JahrgangTypAdmin(SimpleHistoryAdmin):
    search_fields = ['name']