from datetime import datetime, timedelta
import random
from django.contrib import admin
from django.http import HttpResponseRedirect
from django.urls import path
from django.contrib import messages
from django.utils.html import format_html
from .models import (
    Ampel2, Attribute, CustomUser, Einsatzland2, 
    Einsatzstelle2, Feedback, KalenderEvent, PersonCluster, 
    Organisation, Aufgabe2, DokumentColor2, Dokument2, 
    Ordner2, Notfallkontakt2, Post2, AufgabeZwischenschritte2, 
    UserAttribute, UserAufgabenZwischenschritte, UserAufgaben, 
    AufgabenCluster, Bilder2, BilderGallery2, ProfilUser2, Maintenance,
    PostSurveyAnswer, PostSurveyQuestion
)
from TEAM.models import Team
from FW.models import Freiwilliger
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


@admin.register(Organisation)
class OrganisationAdmin(SimpleHistoryAdmin):
    search_fields = ['name']

@admin.register(Ordner2)
class OrdnerAdmin(SimpleHistoryAdmin):
    search_fields = ['ordner_name']
    actions = ['set_person_cluster_freiwilliger']

    def set_person_cluster_freiwilliger(self, request, queryset):
        for ordner in queryset:
            ordner.typ.set(PersonCluster.objects.filter(name='Freiwilliger'))
            ordner.save()

@admin.register(Dokument2)
class DokumentAdmin(SimpleHistoryAdmin):
    search_fields = ['ordner', 'dokument', 'beschreibung']

@admin.register(DokumentColor2)
class DokumentColorAdmin(SimpleHistoryAdmin):
    search_fields = ['name']
    

@admin.register(Attribute)
class AttributeAdmin(admin.ModelAdmin):
    search_fields = ['name']

@admin.register(UserAttribute)
class UserAttributeAdmin(admin.ModelAdmin):
    search_fields = ['user__first_name', 'user__last_name', 'attribute__name']


@admin.register(Einsatzland2)
class EinsatzlandAdmin(admin.ModelAdmin):
    search_fields = ['name']


@admin.register(Einsatzstelle2)
class EinsatzstelleAdmin(admin.ModelAdmin):
    search_fields = ['name']


@admin.register(Notfallkontakt2)
class NotfallkontaktAdmin(admin.ModelAdmin):
    search_fields = ['first_name', 'last_name']
    actions = ['anonymize_user']

    def anonymize_user(self, request, queryset):
        for notfallkontakt in queryset:
            notfallkontakt.first_name = f'{notfallkontakt.first_name[0]} anonymisiert'
            notfallkontakt.last_name = f'{notfallkontakt.last_name[0]} anonymisiert'
            notfallkontakt.phone = None
            notfallkontakt.phone_work = None
            notfallkontakt.email = f'{notfallkontakt.first_name}.{notfallkontakt.last_name}@p0k.de'
            notfallkontakt.save()


@admin.register(Post2)
class PostAdmin(admin.ModelAdmin):
    search_fields = ['title']


@admin.register(Aufgabe2)
class AufgabeAdmin(admin.ModelAdmin):
    search_fields = ['name']
    actions = ['set_person_cluster_typ_incoming', 'set_person_cluster_typ_outgoing', 'set_aufg_cluster_before_operation', 'set_aufg_cluster_during_operation', 'set_aufg_cluster_after_operation']

    def set_person_cluster_typ_incoming(self, request, queryset):
        for aufgabe in queryset:
            aufgabe.person_cluster = PersonCluster.objects.get(name='Incoming')
            aufgabe.save()
    
    def set_person_cluster_typ_outgoing(self, request, queryset):
        for aufgabe in queryset:
            aufgabe.person_cluster = PersonCluster.objects.get(name='Outgoing')
            aufgabe.save()

    def set_aufg_cluster_before_operation(self, request, queryset):
        for aufgabe in queryset:
            aufgabe.faellig_art = AufgabenCluster.objects.filter(type='V').first()
            aufgabe.save()

    def set_aufg_cluster_during_operation(self, request, queryset):
        for aufgabe in queryset:
            aufgabe.faellig_art = AufgabenCluster.objects.filter(type='W').first()
            aufgabe.save()

    def set_aufg_cluster_after_operation(self, request, queryset):
        for aufgabe in queryset:
            aufgabe.faellig_art = AufgabenCluster.objects.filter(type='N').first()
            aufgabe.save()





@admin.register(AufgabeZwischenschritte2)
class AufgabeZwischenschritteAdmin(admin.ModelAdmin):
    search_fields = ['name']


@admin.register(UserAufgabenZwischenschritte)
class UserAufgabenZwischenschritteAdmin(admin.ModelAdmin):
    search_fields = ['user_aufgabe__freiwilliger__user__first_name', 'user_aufgabe__freiwilliger__user__last_name', 'aufgabe_zwischenschritt__name']


@admin.register(Ampel2)
class AmpelAdmin(admin.ModelAdmin):
    search_fields = ['status']

@admin.register(UserAufgaben)
class UserAufgabenAdmin(admin.ModelAdmin):
    search_fields = ['freiwilliger__user__first_name', 'freiwilliger__user__last_name', 'aufgabe__name'] 
    actions = ['send_aufgaben_email']

    def send_aufgaben_email(self, request, queryset):
        for freiwilliger_aufgabe in queryset:
            freiwilliger_aufgabe.send_reminder_email()
        msg = f"Erinnerungen wurden gesendet"
        self.message_user(request, msg)


@admin.register(AufgabenCluster)
class AufgabenClusterAdmin(admin.ModelAdmin):
    search_fields = ['name']


@admin.register(Bilder2)
class BilderAdmin(admin.ModelAdmin):
    search_fields = ['name']
    list_display = ('titel', 'user', 'date_created')

@admin.register(BilderGallery2)
class BilderGalleryAdmin(admin.ModelAdmin):
    search_fields = ['bilder']

@admin.register(Maintenance)
class MaintenanceAdmin(admin.ModelAdmin):
    list_display = ['maintenance_start_time', 'maintenance_end_time']
    search_fields = ['maintenance_start_time', 'maintenance_end_time']

@admin.register(PostSurveyAnswer)
class PostSurveyAnswerAdmin(admin.ModelAdmin):
    search_fields = ['answer_text']

@admin.register(PostSurveyQuestion)
class PostSurveyQuestionAdmin(admin.ModelAdmin):
    search_fields = ['question_text']