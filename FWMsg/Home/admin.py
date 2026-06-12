from django.contrib import admin

from .models import OwnSigninUser


@admin.register(OwnSigninUser)
class OwnSigninUserAdmin(admin.ModelAdmin):
    list_display = ('first_name', 'last_name', 'email', 'person_cluster', 'land', 'org', 'created_at')
    list_filter = ('person_cluster', 'org', 'created_at')
    search_fields = ('first_name', 'last_name', 'email')
