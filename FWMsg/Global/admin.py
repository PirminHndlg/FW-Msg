from datetime import datetime, timedelta
import random
from django.contrib import admin
from django.utils import timezone
from django.http import HttpResponseRedirect
from django.urls import path
from django.contrib import messages
from django.utils.html import format_html
from .models import (
    Ampel2, Attribute, CustomUser, Einsatzland2, 
    Einsatzstelle2, Feedback, KalenderEvent, PersonCluster, 
    Organisation, Aufgabe2, DokumentColor2, Dokument2, 
    Ordner2, Notfallkontakt2, Post2, AufgabeZwischenschritte2, PushSubscription, 
    UserAttribute, UserAufgabenZwischenschritte, UserAufgaben, 
    AufgabenCluster, Bilder2, BilderGallery2, BilderComment, BilderReaction, ProfilUser2, Maintenance,
    PostSurveyAnswer, PostSurveyQuestion, EinsatzstelleNotiz, StickyNote, ChangeRequest
)
from TEAM.models import Team
from FW.models import Freiwilliger
from FWMsg.celery import send_email_aufgaben_daily
from simple_history.admin import SimpleHistoryAdmin

# Register your models here.
@admin.register(CustomUser)
class CustomUserAdmin(SimpleHistoryAdmin):
    search_fields = ['user__username', 'user__email', 'user__first_name', 'user__last_name']
    actions = ['send_registration_email', 'create_small_image', 'create_token']
    list_display = (
        'user',
        'person_cluster',
        'mail_notifications',
        'get_user_email',
        'get_last_login',
        'get_online_status_display',
    )
    list_filter = ('person_cluster', 'mail_notifications', ('einmalpasswort', admin.EmptyFieldListFilter))
    readonly_fields = ('mail_notifications_unsubscribe_auth_key',)

    def get_online_status_display(self, obj):
        return obj.get_online_status_display()
    get_online_status_display.admin_order_field = 'last_seen'

    def get_user_email(self, obj):
        return obj.user.email
    get_user_email.short_description = 'Email'
    get_user_email.admin_order_field = 'user__email'
    
    def get_last_login(self, obj):
        return obj.user.last_login
    get_last_login.short_description = 'Last Login'
    get_last_login.admin_order_field = 'user__last_login'

    def get_queryset(self, request):
        """Override to handle custom ordering for online status."""
        from django.db.models import Case, When, Value, F
        from django.db.models.functions import Coalesce
        
        qs = super().get_queryset(request)
        
        # Check if we're sorting by online status (last_seen)
        ordering = request.GET.get('o', '')
        
        if ordering:
            # Parse the ordering parameter (e.g., '4' for ascending, '-4' for descending)
            # where the number corresponds to the column index
            try:
                order_field_index = int(ordering.lstrip('-'))
                is_descending = ordering.startswith('-')
                
                # Get the list of fields in list_display to match index
                list_display_fields = self.get_list_display(request)
                
                # Check if the ordering is on get_online_status_display
                if order_field_index < len(list_display_fields):
                    field_name = list_display_fields[order_field_index]
                    
                    if field_name == 'get_online_status_display':
                        # Custom ordering for online status:
                        # For ascending: most recent first (online first), NULL last (nie online last)
                        # For descending: NULL first (nie online first), oldest first
                        if is_descending:
                            # Descending: NULL first, then oldest to newest
                            qs = qs.order_by(F('last_seen').asc(nulls_first=True))
                        else:
                            # Ascending: newest to oldest (online first), NULL last
                            qs = qs.order_by(F('last_seen').desc(nulls_last=True))
            except (ValueError, IndexError):
                pass
        
        return qs

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('send_daily_emails/', 
                 self.admin_site.admin_view(self.send_daily_emails), 
                 name='send_daily_emails'),
        ]
        return custom_urls + urls

    def send_registration_email(self, request, queryset):
        count = 0
        for customuser in queryset:
            customuser.send_registration_email()
            count += 1
        self.message_user(request, f"Registration emails sent to {count} users.", messages.SUCCESS)
    send_registration_email.short_description = "Send registration email to selected users"

    def create_small_image(self, request, queryset):
        count = 0
        for customuser in queryset:
            if customuser.profil_picture:
                customuser.create_small_image()
                count += 1
        self.message_user(request, f"Small profile images created for {count} users.", messages.SUCCESS)
    create_small_image.short_description = "Create small profile pictures for selected users"

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
    
    def create_token(self, request, queryset):
        for customuser in queryset:
            customuser.create_token()
        self.message_user(request, f"Tokens created for {queryset.count()} users.", messages.SUCCESS)
    create_token.short_description = "Create tokens for selected users"

@admin.register(PersonCluster)
class PersonClusterAdmin(admin.ModelAdmin):
    list_display = ['name', 'view', 'aufgaben', 'calendar', 'dokumente', 'ampel', 'notfallkontakt', 'bilder', 'posts']
    search_fields = ['name']
    list_filter = ['view', 'aufgaben', 'calendar', 'dokumente', 'ampel', 'notfallkontakt', 'bilder', 'posts']


@admin.register(Feedback)
class FeedbackAdmin(admin.ModelAdmin):
    list_display = ['user', 'get_feedback_preview', 'anonymous']
    search_fields = ['user__username', 'text']
    list_filter = ['anonymous']
    readonly_fields = ['text', 'user', 'anonymous']
    
    def get_feedback_preview(self, obj):
        if len(obj.text) > 100:
            return obj.text[:100] + "..."
        return obj.text
    get_feedback_preview.short_description = 'Feedback'


@admin.register(KalenderEvent)
class KalenderEventAdmin(SimpleHistoryAdmin):
    list_display = ['title', 'start', 'end', 'get_participant_count']
    search_fields = ['title', 'description']
    list_filter = ['start']
    filter_horizontal = ['user']
    
    def get_participant_count(self, obj):
        return obj.user.count()
    get_participant_count.short_description = 'Participants'


@admin.register(Organisation)
class OrganisationAdmin(SimpleHistoryAdmin):
    list_display = ['name', 'email', 'get_user_count']
    search_fields = ['name', 'email']
    
    def get_user_count(self, obj):
        return CustomUser.objects.filter(org=obj).count()
    get_user_count.short_description = 'User Count'


@admin.register(Ordner2)
class OrdnerAdmin(SimpleHistoryAdmin):
    list_display = ['ordner_name', 'color', 'get_dokument_count', 'get_visible_to']
    search_fields = ['ordner_name']
    list_filter = ['color', 'typ']
    filter_horizontal = ['typ']
    actions = ['set_person_cluster_freiwilliger']

    def get_dokument_count(self, obj):
        return Dokument2.objects.filter(ordner=obj).count()
    get_dokument_count.short_description = 'Documents'
    
    def get_visible_to(self, obj):
        return ", ".join([cluster.name for cluster in obj.typ.all()[:3]]) + \
               ("..." if obj.typ.count() > 3 else "")
    get_visible_to.short_description = 'Visible To'

    def set_person_cluster_freiwilliger(self, request, queryset):
        freiwilliger_clusters = PersonCluster.objects.filter(name='Freiwilliger')
        count = 0
        for ordner in queryset:
            ordner.typ.set(freiwilliger_clusters)
            ordner.save()
            count += 1
        self.message_user(request, f"Set cluster 'Freiwilliger' for {count} folders.", messages.SUCCESS)
    set_person_cluster_freiwilliger.short_description = "Set person cluster to 'Freiwilliger'"


@admin.register(Dokument2)
class DokumentAdmin(SimpleHistoryAdmin):
    list_display = ['get_title', 'ordner', 'date_created', 'date_modified', 'get_document_type']
    search_fields = ['titel', 'ordner__ordner_name', 'beschreibung']
    list_filter = ['date_created', 'ordner']
    filter_horizontal = ['darf_bearbeiten']
    readonly_fields = ['date_created', 'date_modified', 'preview_image']
    
    def get_title(self, obj):
        return obj.titel or (obj.dokument.name.split('/')[-1] if obj.dokument else obj.link or "No title")
    get_title.short_description = 'Title'
    
    def get_document_type(self, obj):
        return obj.get_document_suffix().upper() if obj.dokument else "LINK" if obj.link else "NONE"
    get_document_type.short_description = 'Type'


@admin.register(DokumentColor2)
class DokumentColorAdmin(SimpleHistoryAdmin):
    list_display = ['name', 'color', 'color_preview']
    search_fields = ['name']
    
    def color_preview(self, obj):
        return format_html('<div style="background-color:{}; width:30px; height:15px;"></div>', obj.color)
    color_preview.short_description = 'Color Preview'
    

@admin.register(Attribute)
class AttributeAdmin(admin.ModelAdmin):
    list_display = ['name', 'type', 'get_value_preview', 'get_person_clusters']
    search_fields = ['name', 'value_for_choices']
    list_filter = ['type', 'person_cluster']
    filter_horizontal = ['person_cluster']
    
    def get_value_preview(self, obj):
        if obj.value_for_choices and len(obj.value_for_choices) > 50:
            return obj.value_for_choices[:50] + "..."
        return obj.value_for_choices
    get_value_preview.short_description = 'Choices'
    
    def get_person_clusters(self, obj):
        return ", ".join([pc.name for pc in obj.person_cluster.all()[:3]]) + \
               ("..." if obj.person_cluster.count() > 3 else "")
    get_person_clusters.short_description = 'For Groups'


@admin.register(UserAttribute)
class UserAttributeAdmin(admin.ModelAdmin):
    list_display = ['user', 'attribute', 'value']
    search_fields = ['user__first_name', 'user__last_name', 'attribute__name', 'value']
    list_filter = ['attribute']


@admin.register(Einsatzland2)
class EinsatzlandAdmin(admin.ModelAdmin):
    list_display = ['name', 'code']
    search_fields = ['name', 'code']


@admin.register(Einsatzstelle2)
class EinsatzstelleAdmin(admin.ModelAdmin):
    list_display = ['name', 'land']
    search_fields = ['name', 'partnerorganisation', 'arbeitsvorgesetzter']
    list_filter = ['land']
    actions = ['change_number_of_freiwillige_to_one']
    
    def change_number_of_freiwillige_to_one(self, request, queryset):
        for einsatzstelle in queryset:
            einsatzstelle.max_freiwillige = 1
            einsatzstelle.save()
        self.message_user(request, f"Anzahl der Freiwilligen für {queryset.count()} Einsatzstellen aktualisiert.", messages.SUCCESS)
        
    change_number_of_freiwillige_to_one.short_description = "Anzahl der Freiwilligen auf 1 setzen"


@admin.register(Notfallkontakt2)
class NotfallkontaktAdmin(admin.ModelAdmin):
    list_display = ['get_full_name', 'phone', 'email', 'user']
    search_fields = ['first_name', 'last_name', 'email', 'phone']
    actions = ['anonymize_user']

    def get_full_name(self, obj):
        return f"{obj.first_name} {obj.last_name}"
    get_full_name.short_description = 'Full Name'

    def anonymize_user(self, request, queryset):
        count = 0
        for notfallkontakt in queryset:
            notfallkontakt.first_name = f'{notfallkontakt.first_name[0]} anonymisiert'
            notfallkontakt.last_name = f'{notfallkontakt.last_name[0]} anonymisiert'
            notfallkontakt.phone = None
            notfallkontakt.phone_work = None
            notfallkontakt.email = f'{notfallkontakt.first_name}.{notfallkontakt.last_name}@anonymized.org'
            notfallkontakt.save()
            count += 1
        self.message_user(request, f"Anonymized {count} emergency contacts.", messages.SUCCESS)
    anonymize_user.short_description = "Anonymize selected emergency contacts"


@admin.register(Post2)
class PostAdmin(admin.ModelAdmin):
    list_display = ['title', 'user', 'date', 'date_updated', 'has_survey', 'get_cluster_count']
    search_fields = ['title', 'text', 'user__username']
    list_filter = ['has_survey', 'date', 'person_cluster']
    readonly_fields = ['date', 'date_updated']
    filter_horizontal = ['person_cluster', 'already_sent_to']
    
    def get_cluster_count(self, obj):
        return obj.person_cluster.count()
    get_cluster_count.short_description = 'Audience Count'


@admin.register(Aufgabe2)
class AufgabeAdmin(admin.ModelAdmin):
    list_display = ['name', 'faellig_art', 'mitupload', 'requires_submission', 'wiederholung', 'get_cluster_count']
    search_fields = ['name', 'beschreibung']
    list_filter = ['mitupload', 'wiederholung', 'faellig_art', 'requires_submission', 'person_cluster']
    filter_horizontal = ['person_cluster']
    actions = ['set_person_cluster_typ_incoming', 'set_person_cluster_typ_outgoing', 
                'set_aufg_cluster_before_operation', 'set_aufg_cluster_during_operation', 
                'set_aufg_cluster_after_operation']

    def get_cluster_count(self, obj):
        return obj.person_cluster.count()
    get_cluster_count.short_description = 'Audience Count'

    def set_person_cluster_typ_incoming(self, request, queryset):
        try:
            incoming_cluster = PersonCluster.objects.get(name='Incoming')
            for aufgabe in queryset:
                aufgabe.person_cluster = incoming_cluster
                aufgabe.save()
            self.message_user(request, f"Person cluster set to 'Incoming' for {queryset.count()} tasks")
        except:
            self.message_user(request, "Could not find PersonCluster 'Incoming'", level=messages.ERROR)
    
    def set_person_cluster_typ_outgoing(self, request, queryset):
        try:
            outgoing_cluster = PersonCluster.objects.get(name='Outgoing')
            for aufgabe in queryset:
                aufgabe.person_cluster = outgoing_cluster
                aufgabe.save()
            self.message_user(request, f"Person cluster set to 'Outgoing' for {queryset.count()} tasks")
        except:
            self.message_user(request, "Could not find PersonCluster 'Outgoing'", level=messages.ERROR)

    def set_aufg_cluster_before_operation(self, request, queryset):
        before_cluster = AufgabenCluster.objects.filter(type='V').first()
        if not before_cluster:
            self.message_user(request, "Could not find 'Vor Einsatz' task cluster", level=messages.ERROR)
            return
            
        for aufgabe in queryset:
            aufgabe.faellig_art = before_cluster
            aufgabe.save()
        self.message_user(request, f"Task type set to 'Vor Einsatz' for {queryset.count()} tasks")

    def set_aufg_cluster_during_operation(self, request, queryset):
        during_cluster = AufgabenCluster.objects.filter(type='W').first()
        if not during_cluster:
            self.message_user(request, "Could not find 'Während Einsatz' task cluster", level=messages.ERROR)
            return
            
        for aufgabe in queryset:
            aufgabe.faellig_art = during_cluster
            aufgabe.save()
        self.message_user(request, f"Task type set to 'Während Einsatz' for {queryset.count()} tasks")

    def set_aufg_cluster_after_operation(self, request, queryset):
        after_cluster = AufgabenCluster.objects.filter(type='N').first()
        if not after_cluster:
            self.message_user(request, "Could not find 'Nach Einsatz' task cluster", level=messages.ERROR)
            return
            
        for aufgabe in queryset:
            aufgabe.faellig_art = after_cluster
            aufgabe.save()
        self.message_user(request, f"Task type set to 'Nach Einsatz' for {queryset.count()} tasks")


@admin.register(AufgabeZwischenschritte2)
class AufgabeZwischenschritteAdmin(admin.ModelAdmin):
    list_display = ['name', 'aufgabe', 'get_description_preview']
    search_fields = ['name', 'aufgabe__name', 'beschreibung']
    list_filter = ['aufgabe']
    
    def get_description_preview(self, obj):
        if obj.beschreibung and len(obj.beschreibung) > 50:
            return obj.beschreibung[:50] + "..."
        return obj.beschreibung or ""
    get_description_preview.short_description = 'Description'


@admin.register(UserAufgabenZwischenschritte)
class UserAufgabenZwischenschritteAdmin(admin.ModelAdmin):
    list_display = ['get_user_name', 'get_aufgabe_name', 'get_zwischenschritt_name', 'erledigt']
    search_fields = ['user_aufgabe__user__first_name', 'user_aufgabe__user__last_name', 
                    'aufgabe_zwischenschritt__name', 'user_aufgabe__aufgabe__name']
    list_filter = ['erledigt', 'aufgabe_zwischenschritt', 'user_aufgabe__aufgabe']
    
    def get_user_name(self, obj):
        user = obj.user_aufgabe.user
        return f"{user.first_name} {user.last_name}"
    get_user_name.short_description = 'User'
    get_user_name.admin_order_field = 'user_aufgabe__user__first_name'
    
    def get_aufgabe_name(self, obj):
        return obj.user_aufgabe.aufgabe.name
    get_aufgabe_name.short_description = 'Task'
    get_aufgabe_name.admin_order_field = 'user_aufgabe__aufgabe__name'
    
    def get_zwischenschritt_name(self, obj):
        return obj.aufgabe_zwischenschritt.name
    get_zwischenschritt_name.short_description = 'Step'
    get_zwischenschritt_name.admin_order_field = 'aufgabe_zwischenschritt__name'


@admin.register(Ampel2)
class AmpelAdmin(admin.ModelAdmin):
    list_display = ['user', 'get_user_full_name', 'status', 'get_comment_preview', 'date']
    search_fields = ['user__username', 'user__first_name', 'user__last_name', 'comment']
    list_filter = ['status', 'date']
    
    def get_user_full_name(self, obj):
        return f"{obj.user.first_name} {obj.user.last_name}"
    get_user_full_name.short_description = 'Full Name'
    
    def get_comment_preview(self, obj):
        if obj.comment and len(obj.comment) > 50:
            return obj.comment[:50] + "..."
        return obj.comment or ""
    get_comment_preview.short_description = 'Comment'


@admin.register(UserAufgaben)
class UserAufgabenAdmin(admin.ModelAdmin):
    list_display = ['get_user_name', 'aufgabe', 'faellig', 'erledigt', 'pending', 'erledigt_am', 'last_reminder', 'has_file']
    search_fields = ['user__first_name', 'user__last_name', 'aufgabe__name', 'personalised_description'] 
    list_filter = ['erledigt', 'pending', 'faellig', 'aufgabe', 'aufgabe__faellig_art']
    readonly_fields = ['datetime']
    actions = ['send_aufgaben_email', 'mark_as_completed', 'mark_as_pending']

    def get_user_name(self, obj):
        return f"{obj.user.first_name} {obj.user.last_name}"
    get_user_name.short_description = 'User'
    get_user_name.admin_order_field = 'user__first_name'
    
    def has_file(self, obj):
        return bool(obj.file) or bool(obj.file_list)
    has_file.boolean = True
    has_file.short_description = 'Has File'

    def send_aufgaben_email(self, request, queryset):
        count = 0
        for freiwilliger_aufgabe in queryset:
            freiwilliger_aufgabe.send_reminder_email()
            count += 1
        msg = f"Reminders were sent for {count} tasks"
        self.message_user(request, msg)
    
    def mark_as_completed(self, request, queryset):
        now = datetime.now().date()
        count = queryset.filter(erledigt=False).update(erledigt=True, erledigt_am=now, pending=False)
        self.message_user(request, f"{count} tasks marked as completed.")
    mark_as_completed.short_description = "Mark selected tasks as completed"
    
    def mark_as_pending(self, request, queryset):
        count = queryset.filter(pending=False, erledigt=False).update(pending=True)
        self.message_user(request, f"{count} tasks marked as pending.")
    mark_as_pending.short_description = "Mark selected tasks as pending"


@admin.register(AufgabenCluster)
class AufgabenClusterAdmin(admin.ModelAdmin):
    list_display = ['name', 'type', 'get_person_clusters']
    search_fields = ['name']
    list_filter = ['type', 'person_cluster']
    filter_horizontal = ['person_cluster']
    
    def get_person_clusters(self, obj):
        return ", ".join([pc.name for pc in obj.person_cluster.all()[:3]]) + \
               ("..." if obj.person_cluster.count() > 3 else "")
    get_person_clusters.short_description = 'For Groups'


@admin.register(Bilder2)
class BilderAdmin(admin.ModelAdmin):
    list_display = ['titel', 'user', 'get_user_full_name', 'date_created', 'date_updated', 'get_image_count']
    search_fields = ['titel', 'beschreibung', 'user__username', 'user__first_name', 'user__last_name']
    list_filter = ['date_created', 'user']
    
    def get_user_full_name(self, obj):
        return f"{obj.user.first_name} {obj.user.last_name}"
    get_user_full_name.short_description = 'Full Name'
    
    def get_image_count(self, obj):
        return BilderGallery2.objects.filter(bilder=obj).count()
    get_image_count.short_description = 'Images'


@admin.register(BilderGallery2)
class BilderGalleryAdmin(admin.ModelAdmin):
    list_display = ['get_image_name', 'bilder', 'get_bilder_title', 'has_small_image']
    search_fields = ['bilder__titel', 'image']
    list_filter = ['bilder']
    
    def get_image_name(self, obj):
        return obj.image.name.split('/')[-1]
    get_image_name.short_description = 'Image'
    
    def get_bilder_title(self, obj):
        return obj.bilder.titel
    get_bilder_title.short_description = 'Album Title'
    get_bilder_title.admin_order_field = 'bilder__titel'
    
    def has_small_image(self, obj):
        return bool(obj.small_image)
    has_small_image.boolean = True
    has_small_image.short_description = 'Has Small Image'


@admin.register(ProfilUser2)
class ProfilUserAdmin(admin.ModelAdmin):
    list_display = ['user', 'get_user_full_name', 'attribut', 'get_value_preview']
    search_fields = ['user__username', 'user__first_name', 'user__last_name', 'attribut', 'value']
    list_filter = ['attribut']
    
    def get_user_full_name(self, obj):
        return f"{obj.user.first_name} {obj.user.last_name}"
    get_user_full_name.short_description = 'Full Name'
    
    def get_value_preview(self, obj):
        if len(obj.value) > 50:
            return obj.value[:50] + "..."
        return obj.value
    get_value_preview.short_description = 'Value'


@admin.register(Maintenance)
class MaintenanceAdmin(admin.ModelAdmin):
    list_display = ['maintenance_start_time', 'maintenance_end_time', 'is_active', 'duration']
    search_fields = ['maintenance_start_time', 'maintenance_end_time']
    
    def is_active(self, obj):
        now = datetime.now()
        return obj.maintenance_start_time <= now <= obj.maintenance_end_time
    is_active.boolean = True
    is_active.short_description = 'Currently Active'
    
    def duration(self, obj):
        delta = obj.maintenance_end_time - obj.maintenance_start_time
        hours = delta.total_seconds() / 3600
        return f"{hours:.1f} hours"
    duration.short_description = 'Duration'


@admin.register(PostSurveyAnswer)
class PostSurveyAnswerAdmin(admin.ModelAdmin):
    list_display = ['answer_text', 'question', 'get_question_text', 'get_vote_count']
    search_fields = ['answer_text', 'question__question_text']
    list_filter = ['question']
    filter_horizontal = ['votes']
    
    def get_question_text(self, obj):
        return obj.question.question_text
    get_question_text.short_description = 'Question Text'
    get_question_text.admin_order_field = 'question__question_text'
    
    def get_vote_count(self, obj):
        return obj.votes.count()
    get_vote_count.short_description = 'Votes'


@admin.register(PostSurveyQuestion)
class PostSurveyQuestionAdmin(admin.ModelAdmin):
    list_display = ['question_text', 'post', 'get_post_title', 'get_answer_count']
    search_fields = ['question_text', 'post__title']
    list_filter = ['post']
    
    def get_post_title(self, obj):
        return obj.post.title
    get_post_title.short_description = 'Post Title'
    get_post_title.admin_order_field = 'post__title'
    
    def get_answer_count(self, obj):
        return obj.survey_answers.count()
    get_answer_count.short_description = 'Answers'


@admin.register(PushSubscription)
class PushSubscriptionAdmin(admin.ModelAdmin):
    list_display = ['user', 'get_user_full_name', 'name', 'created_at', 'last_used']
    search_fields = ['user__username', 'user__first_name', 'user__last_name', 'name', 'endpoint']
    list_filter = ['created_at', 'last_used']
    readonly_fields = ['created_at', 'endpoint', 'p256dh', 'auth']
    
    def get_user_full_name(self, obj):
        return f"{obj.user.first_name} {obj.user.last_name}"
    get_user_full_name.short_description = 'Full Name'
    get_user_full_name.admin_order_field = 'user__first_name'


@admin.register(EinsatzstelleNotiz)
class EinsatzstelleNotizAdmin(admin.ModelAdmin):
    list_display = ['einsatzstelle', 'user', 'date', 'pinned']
    search_fields = ['einsatzstelle__name', 'notiz']
    list_filter = ['date', 'pinned']

@admin.register(StickyNote)
class StickyNoteAdmin(admin.ModelAdmin):
    list_display = ['user', 'get_user_full_name', 'notiz', 'date', 'pinned', 'priority']
    search_fields = ['user__username', 'user__first_name', 'user__last_name', 'notiz']
    list_filter = ['date', 'pinned', 'priority']

    def get_user_full_name(self, obj):
        return f"{obj.user.first_name} {obj.user.last_name}"
    get_user_full_name.short_description = 'Full Name'
    get_user_full_name.admin_order_field = 'user__first_name'


@admin.register(BilderComment)
class BilderCommentAdmin(SimpleHistoryAdmin):
    list_display = ['bilder', 'user', 'get_comment_preview', 'date_created']
    search_fields = ['bilder__titel', 'user__username', 'user__first_name', 'user__last_name', 'comment']
    list_filter = ['date_created', 'bilder__user']
    raw_id_fields = ['bilder', 'user']

    def get_comment_preview(self, obj):
        return obj.comment[:50] + '...' if len(obj.comment) > 50 else obj.comment
    get_comment_preview.short_description = 'Kommentar Vorschau'


@admin.register(BilderReaction)
class BilderReactionAdmin(SimpleHistoryAdmin):
    list_display = ['bilder', 'user', 'emoji', 'date_created']
    search_fields = ['bilder__titel', 'user__username', 'user__first_name', 'user__last_name']
    list_filter = ['emoji', 'date_created', 'bilder__user']
    raw_id_fields = ['bilder', 'user']


@admin.register(ChangeRequest)
class ChangeRequestAdmin(SimpleHistoryAdmin):
    list_display = ['get_object_name', 'change_type', 'status', 'requested_by', 'created_at', 'reviewed_by']
    list_filter = ['change_type', 'status', 'created_at', 'reviewed_at']
    search_fields = ['requested_by__username', 'requested_by__first_name', 'requested_by__last_name', 'reason']
    readonly_fields = ['created_at', 'reviewed_at']
    raw_id_fields = ['requested_by', 'reviewed_by']
    
    fieldsets = (
        ('Grundinformationen', {
            'fields': ('change_type', 'object_id', 'status')
        }),
        ('Benutzer', {
            'fields': ('requested_by', 'reviewed_by')
        }),
        ('Änderungsdetails', {
            'fields': ('field_changes', 'reason', 'review_comment')
        }),
        ('Zeitstempel', {
            'fields': ('created_at', 'reviewed_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_object_name(self, obj):
        return obj.get_object_name()
    get_object_name.short_description = 'Objekt'
    
    actions = ['approve_requests', 'reject_requests']
    
    def approve_requests(self, request, queryset):
        updated = 0
        for change_request in queryset.filter(status='pending'):
            try:
                change_request.status = 'approved'
                change_request.reviewed_by = request.user
                change_request.reviewed_at = timezone.now()
                change_request.save()
                change_request.apply_changes()
                updated += 1
            except Exception as e:
                messages.error(request, f'Fehler beim Genehmigen von {change_request}: {str(e)}')
        
        if updated:
            messages.success(request, f'{updated} Änderungsanträge wurden genehmigt.')
    approve_requests.short_description = 'Ausgewählte Anträge genehmigen'
    
    def reject_requests(self, request, queryset):
        updated = queryset.filter(status='pending').update(
            status='rejected',
            reviewed_by=request.user,
            reviewed_at=timezone.now()
        )
        if updated:
            messages.success(request, f'{updated} Änderungsanträge wurden abgelehnt.')
    reject_requests.short_description = 'Ausgewählte Anträge ablehnen'