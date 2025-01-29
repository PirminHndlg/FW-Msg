from django.contrib import admin
from .models import CustomUser

# Register your models here.
@admin.register(CustomUser)
class CustomUserAdmin(admin.ModelAdmin):
    search_fields = ['user']
    actions = ['send_registration_email']

    def send_registration_email(self, request, queryset):
        for customuser in queryset:
            customuser.send_registration_email()