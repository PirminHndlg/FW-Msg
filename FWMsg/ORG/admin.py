from django.contrib import admin
from .models import Organisation, Ordner, Dokument

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