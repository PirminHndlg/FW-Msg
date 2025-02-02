from django.contrib import admin
from .models import CustomUser, Feedback

# Register your models here.
@admin.register(CustomUser)
class CustomUserAdmin(admin.ModelAdmin):
    search_fields = ['user']
    actions = ['send_registration_email']
    list_filter = [('einmalpasswort', admin.EmptyFieldListFilter)]

    def send_registration_email(self, request, queryset):
        for customuser in queryset:
            customuser.send_registration_email()

@admin.register(Feedback)
class FeedbackAdmin(admin.ModelAdmin):
    list_display = ['user', 'text', 'anonymous']
    search_fields = ['user__username', 'text']
    list_filter = ['anonymous']
