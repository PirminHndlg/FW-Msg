from django.contrib import admin
from django.http import HttpResponseRedirect
from django.urls import path
from django.contrib import messages
from django.utils.html import format_html
from .models import CustomUser, Feedback, KalenderEvent, Log
from FWMsg.celery import send_email_aufgaben_daily

# Register your models here.
@admin.register(CustomUser)
class CustomUserAdmin(admin.ModelAdmin):
    search_fields = ['user__username', 'user__email']
    actions = ['send_registration_email']
    list_filter = [('einmalpasswort', admin.EmptyFieldListFilter)]
    list_display = ('user', 'org', 'role')
    list_filter = ('org', 'role')

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('send_daily_emails/', 
                 self.admin_site.admin_view(self.send_daily_emails), 
                 name='send_daily_emails'),
        ]
        return custom_urls + urls

    def send_registration_email(self, request, queryset):
        for customuser in queryset:
            customuser.send_registration_email()

    def send_daily_emails(self, request):
        try:
            response = send_email_aufgaben_daily()
            self.message_user(request, f'Daily task emails have been sent successfully. {response}', messages.SUCCESS)
        except Exception as e:
            self.message_user(request, f'Error sending emails: {str(e)}', messages.ERROR)
        return HttpResponseRedirect("../")

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context['show_send_emails_button'] = True
        return super().changelist_view(request, extra_context=extra_context)

@admin.register(Feedback)
class FeedbackAdmin(admin.ModelAdmin):
    list_display = ['user', 'text', 'anonymous']
    search_fields = ['user__username', 'text']
    list_filter = ['anonymous']

@admin.register(KalenderEvent)
class KalenderEventAdmin(admin.ModelAdmin):
    list_display = ['title', 'start', 'end', 'description']
    search_fields = ['title', 'description']
    list_filter = ['start']

@admin.register(Log)
class LogAdmin(admin.ModelAdmin):
    list_display = ('timestamp', 'level', 'user', 'source', 'message')
    list_filter = ('level', 'source', 'timestamp')
    search_fields = ('message', 'user__username', 'source')
    readonly_fields = ('timestamp', 'level', 'user', 'message', 'source', 'trace')
    date_hierarchy = 'timestamp'
    ordering = ('-timestamp',)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
