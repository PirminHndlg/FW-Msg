from django.contrib import admin
from .models import Organisation, Ordner, Dokument, Referenten, JahrgangTyp, DokumentColor
from simple_history.admin import SimpleHistoryAdmin

# Register your models here.
@admin.register(Organisation)
class OrganisationAdmin(SimpleHistoryAdmin):
    search_fields = ['name']

@admin.register(Ordner)
class OrdnerAdmin(SimpleHistoryAdmin):
    search_fields = ['ordner_name']

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
