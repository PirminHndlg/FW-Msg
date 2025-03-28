from django.contrib import admin
from django.http import HttpResponseRedirect
from django.urls import path
from django.contrib import messages
from django.utils.html import format_html
from .models import CustomUser, Feedback, KalenderEvent, PersonCluster
from FWMsg.celery import send_email_aufgaben_daily
from simple_history.admin import SimpleHistoryAdmin

# Register your models here.
@admin.register(CustomUser)
class CustomUserAdmin(SimpleHistoryAdmin):
    search_fields = ['user__username', 'user__email']
    actions = ['send_registration_email', 'create_small_image']
    list_filter = [('einmalpasswort', admin.EmptyFieldListFilter)]
    list_display = ('user', 'org')
    list_filter = ('org',)

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

    def create_small_image(self, request, queryset):
        for customuser in queryset:
            customuser.create_small_image()

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

@admin.register(PersonCluster)
class PersonClusterAdmin(admin.ModelAdmin):
    list_display = ['name', 'view']
    search_fields = ['name']
    list_filter = ['view']


@admin.register(Feedback)
class FeedbackAdmin(admin.ModelAdmin):
    list_display = ['user', 'text', 'anonymous']
    search_fields = ['user__username', 'text']
    list_filter = ['anonymous']

@admin.register(KalenderEvent)
class KalenderEventAdmin(SimpleHistoryAdmin):
    list_display = ['title', 'start', 'end', 'description']
    search_fields = ['title', 'description']
    list_filter = ['start']
