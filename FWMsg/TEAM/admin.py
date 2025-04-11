from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin
from .models import Team

# Register your models here.
@admin.register(Team)
class TeamAdmin(SimpleHistoryAdmin):
    search_fields = ['user__first_name', 'user__last_name', 'user__email']
    actions = ['anonymize_user']

    def anonymize_user(self, request, queryset):
        for referent in queryset:
            referent.user.email = f'{referent.user.first_name[0]}.{referent.user.last_name[0]}@p0k.de'
            referent.user.save()