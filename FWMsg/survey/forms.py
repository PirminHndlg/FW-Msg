from django import forms
from django.utils.translation import gettext_lazy as _
from django.contrib.auth.models import User
from .models import Survey, SurveyQuestion, SurveyQuestionOption, SurveyResponse, SurveyAnswer


class SurveyForm(forms.ModelForm):
    """Form for creating and editing surveys"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Ensure initial values are formatted as YYYY-MM-DD for HTML5 date input
        for field in ['start_date', 'end_date']:
            value = self.initial.get(field) or self.instance and getattr(self.instance, field, None)
            if value:
                if hasattr(value, 'strftime'):
                    self.initial[field] = value.strftime('%Y-%m-%d')
                elif isinstance(value, str) and '.' in value:
                    # Try to parse DD.MM.YYYY
                    import datetime
                    try:
                        dt = datetime.datetime.strptime(value, '%d.%m.%Y')
                        self.initial[field] = dt.strftime('%Y-%m-%d')
                    except Exception:
                        pass

    class Meta:
        model = Survey
        fields = [
            'title', 'description', 'allow_anonymous', 'responses_are_anonymous',
            'start_date', 'end_date', 'max_responses'
        ]
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': _('Enter survey title')
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': _('Optional description of the survey')
            }),
            'allow_anonymous': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'responses_are_anonymous': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'start_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }, format='%Y-%m-%d'),
            'end_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }, format='%Y-%m-%d'),
            'max_responses': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '1'
            }),
        }


class SurveyQuestionForm(forms.ModelForm):
    """Form for creating and editing survey questions"""
    
    class Meta:
        model = SurveyQuestion
        fields = [
            'question_text', 'question_type', 'is_required', 
            'order', 'help_text'
        ]
        widgets = {
            'question_text': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': _('Enter your question')
            }),
            'question_type': forms.Select(attrs={
                'class': 'form-select'
            }),
            'is_required': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'order': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '-1'
            }),
            'help_text': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': _('Optional help text for participants')
            }),
        }


class SurveyQuestionOptionForm(forms.ModelForm):
    """Form for creating question options"""
    
    class Meta:
        model = SurveyQuestionOption
        fields = ['option_text', 'order']
        widgets = {
            'option_text': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': _('Enter option text')
            }),
            'order': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '-1'
            }),
        }


class SurveyParticipationForm(forms.Form):
    """Dynamic form for survey participation"""
    
    def __init__(self, survey, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.survey = survey
        self.org = survey.org
        
        for question in survey.questions.all():
            field_name = f'question_{question.id}'
            field_kwargs = {
                'label': question.question_text,
                'required': question.is_required,
                'help_text': question.help_text,
            }
            
            if question.question_type == 'text':
                self.fields[field_name] = forms.CharField(
                    widget=forms.TextInput(attrs={'class': 'form-control'}),
                    **field_kwargs
                )
            
            elif question.question_type == 'textarea':
                self.fields[field_name] = forms.CharField(
                    widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
                    **field_kwargs
                )
            
            elif question.question_type == 'email':
                self.fields[field_name] = forms.EmailField(
                    widget=forms.EmailInput(attrs={'class': 'form-control', 'autocomplete': 'email'}),
                    **field_kwargs
                )
            
            elif question.question_type == 'number':
                self.fields[field_name] = forms.IntegerField(
                    widget=forms.NumberInput(attrs={'class': 'form-control'}),
                    **field_kwargs
                )
            
            elif question.question_type == 'date':
                self.fields[field_name] = forms.DateField(
                    widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
                    **field_kwargs
                )
            
            elif question.question_type == 'rating':
                choices = [(i, str(i)) for i in range(1, 6)]
                self.fields[field_name] = forms.ChoiceField(
                    choices=choices,
                    widget=forms.RadioSelect(attrs={'class': 'form-check-input'}),
                    **field_kwargs
                )
            
            elif question.question_type == 'select':
                choices = [('', _('Select an option'))]
                choices.extend([
                    (option.id, option.option_text) 
                    for option in question.options.all()
                ])
                self.fields[field_name] = forms.ChoiceField(
                    choices=choices,
                    widget=forms.Select(attrs={'class': 'form-select'}),
                    **field_kwargs
                )
            
            elif question.question_type == 'radio':
                choices = [
                    (option.id, option.option_text) 
                    for option in question.options.all()
                ]
                if choices:
                    self.fields[field_name] = forms.ChoiceField(
                        choices=choices,
                        widget=forms.RadioSelect(attrs={'class': 'form-check-input'}),
                        **field_kwargs
                    )
            
            elif question.question_type == 'checkbox':
                choices = [
                    (option.id, option.option_text) 
                    for option in question.options.all()
                ]
                if choices:
                    self.fields[field_name] = forms.MultipleChoiceField(
                        choices=choices,
                        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'}),
                        **field_kwargs
                    )
    
    def save_response(self, survey, user=None, session_key=None, ip_address=None):
        """Save the form data as a survey response"""
        # If survey is set to anonymous responses, don't save user information
        if survey.responses_are_anonymous:
            user = None
            session_key = None
            ip_address = None
        
        response = SurveyResponse.objects.create(
            survey=survey,
            respondent=user,
            session_key=session_key,
            ip_address=ip_address,
            is_complete=True,
            org=survey.org
        )
        
        for question in survey.questions.all():
            field_name = f'question_{question.id}'
            if field_name in self.cleaned_data:
                answer_data = self.cleaned_data[field_name]
                
                # Create the answer
                answer = SurveyAnswer.objects.create(
                    response=response,
                    question=question,
                    org=survey.org
                )
                
                if question.question_type in ['checkbox']:
                    # Handle multiple choice questions
                    if answer_data:
                        option_ids = [int(opt_id) for opt_id in answer_data]
                        options = SurveyQuestionOption.objects.filter(
                            id__in=option_ids,
                            question=question
                        )
                        answer.selected_options.set(options)
                
                elif question.question_type in ['select', 'radio']:
                    # Handle single choice questions
                    if answer_data:
                        try:
                            option = SurveyQuestionOption.objects.get(
                                id=int(answer_data),
                                question=question
                            )
                            answer.selected_options.add(option)
                        except (ValueError, SurveyQuestionOption.DoesNotExist):
                            pass
                
                else:
                    # Handle text-based questions
                    answer.text_answer = str(answer_data) if answer_data else ''
                    answer.save()
        
        return response


# Formset for managing multiple question options
SurveyQuestionOptionFormSet = forms.inlineformset_factory(
    SurveyQuestion,
    SurveyQuestionOption,
    form=SurveyQuestionOptionForm,
    extra=3,
    can_delete=True,
    min_num=0,
    validate_min=False
) 