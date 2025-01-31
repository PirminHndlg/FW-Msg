from django.contrib import admin
from .models import Organisation, Ordner, Dokument, Referenten

# Register your models here.
@admin.register(Organisation)
class OrganisationAdmin(admin.ModelAdmin):
    search_fields = ['name']

@admin.register(Ordner)
class OrdnerAdmin(admin.ModelAdmin):
    search_fields = ['ordner_name']

@admin.register(Dokument)
class DokumentAdmin(admin.ModelAdmin):
    search_fields = ['ordner', 'dokument', 'beschreibung']

@admin.register(Referenten)
class ReferentenAdmin(admin.ModelAdmin):
    search_fields = ['first_name', 'last_name', 'email', 'phone']
