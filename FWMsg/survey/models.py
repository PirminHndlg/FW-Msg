from datetime import date
import uuid
import secrets
from django.db import models
from django.contrib.auth.models import User
from django.utils.translation import gettext_lazy as _
from django.urls import reverse
from Global.models import OrgModel


def generate_survey_key():
    """Generate a secure random key for survey access"""
    return secrets.token_urlsafe(32)


class Survey(OrgModel):
    """Main survey model"""
    QUESTION_TYPES = [
        ('text', _('Text')),
        ('textarea', _('Textarea')),
        ('select', _('Single Choice')),
        ('checkbox', _('Multiple Choice')),
        ('radio', _('Radio Button')),
        ('email', _('Email')),
        ('number', _('Number')),
    ]
    
    title = models.CharField(max_length=200, verbose_name=_('Title'))
    description = models.TextField(blank=True, verbose_name=_('Description'))
    survey_key = models.CharField(
        max_length=50, 
        unique=True, 
        default=generate_survey_key,
        verbose_name=_('Survey Key')
    )
    created_by = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        verbose_name=_('Created by')
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_('Created at'))
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_('Updated at'))
    is_active = models.BooleanField(default=True, verbose_name=_('Is active'))
    allow_anonymous = models.BooleanField(
        default=False, 
        verbose_name=_('Allow anonymous participation')
    )
    start_date = models.DateField(
        null=True, blank=True, 
        verbose_name=_('Start date')
    )
    end_date = models.DateField(
        null=True, blank=True, 
        verbose_name=_('End date')
    )
    max_responses = models.PositiveIntegerField(
        null=True, blank=True,
        verbose_name=_('Maximum responses')
    )
    
    class Meta:
        verbose_name = _('Survey')
        verbose_name_plural = _('Surveys')
        ordering = ['-created_at']
    
    def __str__(self):
        return self.title
    
    def get_absolute_url(self):
        return reverse('survey:survey_detail', kwargs={'survey_key': self.survey_key})
    
    def is_accessible(self):
        """Check if survey is accessible based on dates and status"""
        now = date.today()
        if not self.is_active:
            return False
        if self.start_date and now < self.start_date:
            return False
        if self.end_date and now > self.end_date:
            return False
        if self.max_responses and self.response_count() >= self.max_responses:
            return False
        return True
    
    def response_count(self):
        return SurveyResponse.objects.filter(survey=self, is_complete=True).count()


class SurveyQuestion(OrgModel):
    """Survey question model"""
    QUESTION_TYPES = [
        ('text', _('Short Text')),
        ('textarea', _('Long Text')),
        ('select', _('Dropdown')),
        ('radio', _('Radio Buttons')),
        ('checkbox', _('Checkboxes')),
        ('email', _('Email')),
        ('number', _('Number')),
        ('date', _('Date')),
        ('rating', _('Rating (1-5)')),
    ]
    
    survey = models.ForeignKey(
        Survey, 
        on_delete=models.CASCADE, 
        related_name='questions',
        verbose_name=_('Survey')
    )
    question_text = models.CharField(max_length=500, verbose_name=_('Question'))
    question_type = models.CharField(
        max_length=20, 
        choices=QUESTION_TYPES, 
        default='text',
        verbose_name=_('Question Type')
    )
    is_required = models.BooleanField(default=False, verbose_name=_('Required'))
    order = models.PositiveIntegerField(default=0, verbose_name=_('Order'))
    help_text = models.CharField(
        max_length=200, 
        blank=True, 
        verbose_name=_('Help text')
    )
    
    class Meta:
        verbose_name = _('Survey Question')
        verbose_name_plural = _('Survey Questions')
        ordering = ['order']
    
    def __str__(self):
        return f"{self.survey.title} - {self.question_text[:50]}"


class SurveyQuestionOption(OrgModel):
    """Options for select, radio, and checkbox questions"""
    question = models.ForeignKey(
        SurveyQuestion, 
        on_delete=models.CASCADE, 
        related_name='options',
        verbose_name=_('Question')
    )
    option_text = models.CharField(max_length=200, verbose_name=_('Option text'))
    order = models.PositiveIntegerField(default=0, verbose_name=_('Order'))
    
    class Meta:
        verbose_name = _('Question Option')
        verbose_name_plural = _('Question Options')
        ordering = ['order']
    
    def __str__(self):
        return f"{self.question.question_text[:30]} - {self.option_text}"


class SurveyResponse(OrgModel):
    """Survey response from a participant"""
    survey = models.ForeignKey(
        Survey, 
        on_delete=models.CASCADE, 
        related_name='responses',
        verbose_name=_('Survey')
    )
    respondent = models.ForeignKey(
        User, 
        null=True, blank=True,
        on_delete=models.SET_NULL,
        verbose_name=_('Respondent')
    )
    session_key = models.CharField(
        max_length=40, 
        null=True, blank=True,
        verbose_name=_('Session key')
    )
    ip_address = models.GenericIPAddressField(
        null=True, blank=True,
        verbose_name=_('IP Address')
    )
    submitted_at = models.DateTimeField(auto_now_add=True, verbose_name=_('Submitted at'))
    is_complete = models.BooleanField(default=False, verbose_name=_('Is complete'))
    
    class Meta:
        verbose_name = _('Survey Response')
        verbose_name_plural = _('Survey Responses')
        ordering = ['-submitted_at']
        unique_together = ['survey', 'respondent', 'session_key']
    
    def __str__(self):
        respondent_info = self.respondent.username if self.respondent else f"Anonymous ({self.session_key[:8]})"
        return f"{self.survey.title} - {respondent_info}"


class SurveyAnswer(OrgModel):
    """Individual answer to a survey question"""
    response = models.ForeignKey(
        SurveyResponse, 
        on_delete=models.CASCADE, 
        related_name='answers',
        verbose_name=_('Response')
    )
    question = models.ForeignKey(
        SurveyQuestion, 
        on_delete=models.CASCADE,
        verbose_name=_('Question')
    )
    text_answer = models.TextField(blank=True, verbose_name=_('Text answer'))
    selected_options = models.ManyToManyField(
        SurveyQuestionOption, 
        blank=True,
        verbose_name=_('Selected options')
    )
    
    class Meta:
        verbose_name = _('Survey Answer')
        verbose_name_plural = _('Survey Answers')
        unique_together = ['response', 'question']
    
    def __str__(self):
        return f"{self.response} - {self.question.question_text[:30]}"
