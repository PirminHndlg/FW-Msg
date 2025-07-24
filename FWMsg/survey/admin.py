from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from .models import Survey, SurveyQuestion, SurveyQuestionOption, SurveyResponse, SurveyAnswer


class SurveyQuestionOptionInline(admin.TabularInline):
    """Inline for managing question options"""
    model = SurveyQuestionOption
    extra = 2
    fields = ['option_text', 'order']
    ordering = ['order']


class SurveyQuestionInline(admin.TabularInline):
    """Inline for managing survey questions"""
    model = SurveyQuestion
    extra = 1
    fields = ['question_text', 'question_type', 'is_required', 'order']
    ordering = ['order']
    show_change_link = True


class SurveyAnswerInline(admin.TabularInline):
    """Inline for viewing survey answers"""
    model = SurveyAnswer
    extra = 0
    readonly_fields = ['question', 'text_answer', 'get_selected_options']
    fields = ['question', 'text_answer', 'get_selected_options']
    
    def get_selected_options(self, obj):
        if obj.pk:
            options = obj.selected_options.all()
            if options:
                return ', '.join([opt.option_text for opt in options])
        return '-'
    get_selected_options.short_description = _('Selected Options')


@admin.register(Survey)
class SurveyAdmin(admin.ModelAdmin):
    """Admin interface for Survey model"""
    list_display = [
        'title', 'created_by', 'is_active', 'allow_anonymous', 
        'response_count', 'question_count', 'created_at', 'survey_link'
    ]
    list_filter = [
        'is_active', 'allow_anonymous', 'created_at', 
        'start_date', 'end_date'
    ]
    search_fields = ['title', 'description', 'created_by__username']
    readonly_fields = ['survey_key', 'created_at', 'updated_at', 'survey_link']
    inlines = [SurveyQuestionInline]
    
    fieldsets = (
        (_('Basic Information'), {
            'fields': ('title', 'description', 'created_by')
        }),
        (_('Access Settings'), {
            'fields': ('survey_key', 'is_active', 'allow_anonymous')
        }),
        (_('Schedule & Limits'), {
            'fields': ('start_date', 'end_date', 'max_responses'),
            'classes': ('collapse',)
        }),
        (_('System Information'), {
            'fields': ('created_at', 'updated_at', 'survey_link'),
            'classes': ('collapse',)
        }),
    )
    
    def response_count(self, obj):
        return obj.responses.filter(is_complete=True).count()
    response_count.short_description = _('Responses')
    response_count.admin_order_field = 'response_count'
    
    def question_count(self, obj):
        return obj.questions.count()
    question_count.short_description = _('Questions')
    
    def survey_link(self, obj):
        if obj.pk:
            url = reverse('survey:survey_detail', kwargs={'survey_key': obj.survey_key})
            return format_html(
                '<a href="{}" target="_blank">{}</a>',
                url,
                _('View Survey')
            )
        return '-'
    survey_link.short_description = _('Public Link')
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.prefetch_related('questions', 'responses')
    
    def save_model(self, request, obj, form, change):
        if not change:  # New object
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(SurveyQuestion)
class SurveyQuestionAdmin(admin.ModelAdmin):
    """Admin interface for SurveyQuestion model"""
    list_display = [
        'survey', 'question_text_short', 'question_type', 
        'is_required', 'order', 'option_count'
    ]
    list_filter = ['question_type', 'is_required', 'survey']
    search_fields = ['question_text', 'survey__title']
    inlines = [SurveyQuestionOptionInline]
    ordering = ['survey', 'order']
    
    fieldsets = (
        (_('Question Details'), {
            'fields': ('survey', 'question_text', 'question_type')
        }),
        (_('Settings'), {
            'fields': ('is_required', 'order', 'help_text')
        }),
    )
    
    def question_text_short(self, obj):
        return obj.question_text[:50] + '...' if len(obj.question_text) > 50 else obj.question_text
    question_text_short.short_description = _('Question')
    
    def option_count(self, obj):
        return obj.options.count()
    option_count.short_description = _('Options')


@admin.register(SurveyQuestionOption)
class SurveyQuestionOptionAdmin(admin.ModelAdmin):
    """Admin interface for SurveyQuestionOption model"""
    list_display = ['question', 'option_text', 'order']
    list_filter = ['question__survey', 'question__question_type']
    search_fields = ['option_text', 'question__question_text']
    ordering = ['question', 'order']


@admin.register(SurveyResponse)
class SurveyResponseAdmin(admin.ModelAdmin):
    """Admin interface for SurveyResponse model"""
    list_display = [
        'survey', 'respondent_info', 'is_complete', 
        'submitted_at', 'ip_address'
    ]
    list_filter = [
        'is_complete', 'submitted_at', 'survey'
    ]
    search_fields = [
        'survey__title', 'respondent__username', 
        'respondent__email', 'ip_address'
    ]
    readonly_fields = [
        'survey', 'respondent', 'session_key', 
        'ip_address', 'submitted_at', 'is_complete'
    ]
    inlines = [SurveyAnswerInline]
    
    def respondent_info(self, obj):
        if obj.respondent:
            return f"{obj.respondent.username} ({obj.respondent.email})"
        else:
            return f"Anonymous ({obj.session_key[:8]}...)"
    respondent_info.short_description = _('Respondent')
    
    def has_add_permission(self, request):
        # Prevent manual creation of responses through admin
        return False
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('survey', 'respondent').prefetch_related('answers')


@admin.register(SurveyAnswer)
class SurveyAnswerAdmin(admin.ModelAdmin):
    """Admin interface for SurveyAnswer model"""
    list_display = [
        'response', 'question_short', 'answer_preview', 
        'selected_options_preview'
    ]
    list_filter = [
        'response__survey', 'question__question_type',
        'response__submitted_at'
    ]
    search_fields = [
        'text_answer', 'question__question_text',
        'response__survey__title'
    ]
    readonly_fields = [
        'response', 'question', 'text_answer', 
        'selected_options'
    ]
    
    def question_short(self, obj):
        return obj.question.question_text[:30] + '...' if len(obj.question.question_text) > 30 else obj.question.question_text
    question_short.short_description = _('Question')
    
    def answer_preview(self, obj):
        if obj.text_answer:
            return obj.text_answer[:50] + '...' if len(obj.text_answer) > 50 else obj.text_answer
        return '-'
    answer_preview.short_description = _('Text Answer')
    
    def selected_options_preview(self, obj):
        options = obj.selected_options.all()
        if options:
            return ', '.join([opt.option_text for opt in options[:3]])
        return '-'
    selected_options_preview.short_description = _('Selected Options')
    
    def has_add_permission(self, request):
        # Prevent manual creation of answers through admin
        return False
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related(
            'response__survey', 'question'
        ).prefetch_related('selected_options')


# Custom admin site configuration
admin.site.site_header = _('FWMsg Survey Administration')
admin.site.site_title = _('Survey Admin')
admin.site.index_title = _('Survey Management')
