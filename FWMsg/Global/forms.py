from django import forms
from .models import Feedback, Post2, Notfallkontakt2, PostSurveyQuestion, PostSurveyAnswer
from django.utils.translation import gettext_lazy as _

class FeedbackForm(forms.ModelForm):
    class Meta:
        model = Feedback
        fields = ['text', 'anonymous']

class AddNotifallkontaktForm(forms.ModelForm):
    class Meta:
        model = Notfallkontakt2
        fields = ['first_name', 'last_name', 'phone_work', 'phone', 'email']

class AddPostForm(forms.ModelForm):
    has_survey = forms.BooleanField(required=False, label=_('Umfrage hinzufügen'), 
                                  help_text=_('Aktivieren, um eine einfache Umfrage zum Beitrag hinzuzufügen'))
    survey_question = forms.CharField(required=False, max_length=200, 
                                    label=_('Umfragefrage'), 
                                    help_text=_('Geben Sie die Frage für Ihre Umfrage ein'))
    
    # Dynamic answer fields
    answer_1 = forms.CharField(required=False, max_length=100, 
                             label=_('Antwort 1'), 
                             help_text=_('Erste Antwortmöglichkeit'))
    answer_2 = forms.CharField(required=False, max_length=100, 
                             label=_('Antwort 2'), 
                             help_text=_('Zweite Antwortmöglichkeit'))
    answer_3 = forms.CharField(required=False, max_length=100, 
                             label=_('Antwort 3'), 
                             help_text=_('Dritte Antwortmöglichkeit (optional)'))
    answer_4 = forms.CharField(required=False, max_length=100, 
                             label=_('Antwort 4'), 
                             help_text=_('Vierte Antwortmöglichkeit (optional)'))
    answer_5 = forms.CharField(required=False, max_length=100, 
                             label=_('Antwort 5'), 
                             help_text=_('Fünfte Antwortmöglichkeit (optional)'))
    
    class Meta:
        model = Post2
        fields = ['title', 'text', 'has_survey']
        widgets = {
            'text': forms.Textarea(attrs={'rows': 10}),
        }
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['title'].widget.attrs.update({'placeholder': _('Titel des Beitrags')})
        self.fields['text'].widget.attrs.update({'placeholder': _('Inhalt des Beitrags')})
        
    def clean(self):
        cleaned_data = super().clean()
        has_survey = cleaned_data.get('has_survey')
        
        if has_survey:
            # Survey question is required if has_survey is checked
            survey_question = cleaned_data.get('survey_question')
            if not survey_question:
                self.add_error('survey_question', _('Bitte geben Sie eine Frage für die Umfrage ein'))
                
            # At least two answers are required
            answer_1 = cleaned_data.get('answer_1')
            answer_2 = cleaned_data.get('answer_2')
            
            if not answer_1:
                self.add_error('answer_1', _('Mindestens zwei Antwortmöglichkeiten sind erforderlich'))
            if not answer_2:
                self.add_error('answer_2', _('Mindestens zwei Antwortmöglichkeiten sind erforderlich'))
                
        return cleaned_data
    
    def save(self, commit=True):
        post = super().save(commit=False)
        post.has_survey = self.cleaned_data.get('has_survey', False)
        
        if commit:
            post.save()
            
            # Create survey question and answers if has_survey is checked
            if post.has_survey:
                question_text = self.cleaned_data.get('survey_question')
                if question_text:
                    # Create or update the survey question
                    question, created = PostSurveyQuestion.objects.update_or_create(
                        post=post,
                        org=post.org,
                        defaults={'question_text': question_text}
                    )
                    
                    # Delete existing answers if updating
                    if not created:
                        PostSurveyAnswer.objects.filter(question=question).delete()
                    
                    # Create answers
                    for i in range(1, 6):
                        answer_text = self.cleaned_data.get(f'answer_{i}')
                        if answer_text:
                            PostSurveyAnswer.objects.create(
                                question=question,
                                org=post.org,
                                answer_text=answer_text
                            )
                            
        return post