from django.contrib import admin
from .models import Organisation

# Register your models here.
@admin.register(Organisation)
class OrganisationAdmin(admin.ModelAdmin):
    search_fields = ['name']