from django import forms

from FWMsg.middleware import get_current_request
from .models import Feedback, PersonCluster, Post2, Notfallkontakt2, PostSurveyQuestion, PostSurveyAnswer, EinsatzstelleNotiz
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
        fields = ['title', 'text', 'has_survey', 'person_cluster']
        widgets = {
            'text': forms.Textarea(attrs={'rows': 10}),
            'person_cluster': forms.CheckboxSelectMultiple(),
        }

        
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['title'].widget.attrs.update({'placeholder': _('Titel des Beitrags')})
        self.fields['text'].widget.attrs.update({'placeholder': _('Inhalt des Beitrags')})
        self.fields['person_cluster'].widget.attrs.update({'class': 'form-check-input'})

        # Get all person clusters
        request = get_current_request()
        if request and hasattr(request, 'user') and hasattr(request.user, 'customuser'):
            
            # Filter queryset based on user role
            if request.user.role == 'O':
                self.fields['person_cluster'].queryset = PersonCluster.objects.filter(
                    org=request.user.org
                ).order_by('name')
                self.fields['person_cluster'].required = False
            else:
                # For non-admin users, just show their own person_cluster
                person_cluster_id = request.user.person_cluster.id
                self.fields['person_cluster'].queryset = PersonCluster.objects.filter(
                    id=person_cluster_id
                )
                # Pre-select their cluster
                if not self.instance.pk:  # Only for new instances
                    self.initial['person_cluster'] = [person_cluster_id]
            
                self.fields['person_cluster'].widget.attrs.update({'disabled': 'true'})
            
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
            # Save the ManyToManyField
            self.save_m2m()
            self.save_answers()
        
        return post
    
    def save_answers(self):
        # Create survey question and answers if has_survey is checked
        if self.instance.has_survey:
            question_text = self.cleaned_data.get('survey_question')
            if question_text:
                # Create or update the survey question
                question, created = PostSurveyQuestion.objects.update_or_create(
                    post=self.instance,
                    org=self.instance.org,
                    defaults={'question_text': question_text}
                )

                if not created:
                    # Get existing answers to compare with new ones
                    existing_answers = {answer.answer_text: answer for answer in 
                                      PostSurveyAnswer.objects.filter(question=question)}
                    
                    # Collect new answers
                    new_answers = []
                    for i in range(1, 6):
                        answer_text = self.cleaned_data.get(f'answer_{i}')
                        if answer_text:
                            new_answers.append(answer_text)
                    
                    # Check if answers have changed
                    answers_changed = len(existing_answers) != len(new_answers)
                    if not answers_changed:
                        for answer_text in new_answers:
                            if answer_text not in existing_answers:
                                answers_changed = True
                                break
                    
                    # Only delete old answers if there were changes
                    if answers_changed:
                        PostSurveyAnswer.objects.filter(question=question).delete()
                        # Create new answers
                        for answer_text in new_answers:
                            PostSurveyAnswer.objects.create(
                                question=question,
                                org=self.instance.org,
                                answer_text=answer_text
                            )
                    else:
                        # No changes to answers, do nothing
                        pass
                else:
                    # This is a new question, create all answers
                    for i in range(1, 6):
                        answer_text = self.cleaned_data.get(f'answer_{i}')
                        if answer_text:
                            PostSurveyAnswer.objects.create(
                                question=question,
                                org=self.instance.org,
                                answer_text=answer_text
                            )
                
class EinsatzstelleNotizForm(forms.ModelForm):
    class Meta:
        model = EinsatzstelleNotiz
        fields = ['notiz']
        exclude = ['einsatzstelle']

    def __init__(self, *args, **kwargs):
        self.org = kwargs.pop('org', None)
        self.einsatzstelle = kwargs.pop('einsatzstelle', None)
        self.request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
        self.fields['notiz'].widget.attrs.update({'placeholder': _('Notiz')})
        self.fields['notiz'].required = True
        
    def save(self, commit=True):
        notiz = super().save(commit=False)
        notiz.user = self.request.user
        notiz.org = self.org
        notiz.einsatzstelle = self.einsatzstelle
        if commit:
            notiz.save()
        return notiz
