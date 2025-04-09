from django.contrib import admin
from .models import Ordner, Dokument, Referenten, JahrgangTyp, DokumentColor
from simple_history.admin import SimpleHistoryAdmin

# Register your models here.

@admin.register(Ordner)
class OrdnerAdmin(SimpleHistoryAdmin):
    search_fields = ['ordner_name']
    actions = ['all_to_incoming', 'all_to_outgoing']

    def all_to_incoming(self, request, queryset):
        for ordner in queryset:
            ordner.typ = JahrgangTyp.objects.get(name='Incoming')
            ordner.save()
            
    def all_to_outgoing(self, request, queryset):
        for ordner in queryset:
            ordner.typ = JahrgangTyp.objects.get(name='Outgoing')
            ordner.save()

@admin.register(Dokument)
class DokumentAdmin(SimpleHistoryAdmin):
    search_fields = ['ordner', 'dokument', 'beschreibung']

@admin.register(DokumentColor)
class DokumentColorAdmin(SimpleHistoryAdmin):
    search_fields = ['name']

@admin.register(Referenten)
class ReferentenAdmin(SimpleHistoryAdmin):
    search_fields = ['first_name', 'last_name', 'email', 'phone']
    actions = ['anonymize_user']

    def anonymize_user(self, request, queryset):
        for referent in queryset:
            referent.email = f'{referent.first_name[0]}.{referent.last_name[0]}@p0k.de'
            referent.user.email = f'{referent.first_name[0]}.{referent.last_name[0]}@p0k.de'
            referent.phone_work = None
            referent.phone_mobil = None
            referent.save()
            referent.user.save()

@admin.register(JahrgangTyp)
class JahrgangTypAdmin(SimpleHistoryAdmin):
    search_fields = ['name']