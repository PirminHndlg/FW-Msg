from datetime import datetime
import random
import string
from django import forms
from django.contrib.auth.models import User
from Global.models import CustomUser, PersonCluster
from .models import ApplicationQuestion, ApplicationAnswer, Bewerber, ApplicationAnswerFile
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _


class CreateAccountForm(forms.Form):
    first_name = forms.CharField(max_length=150, required=True, label='Vorname')
    last_name = forms.CharField(max_length=150, required=True, label='Nachname')
    email = forms.EmailField(required=True, label='Email')
    password = forms.CharField(
        max_length=150, 
        required=True, 
        label='Passwort',
        help_text=_('Ihr Passwort muss folgende Anforderungen erfüllen:<br>• Mindestens 8 Zeichen lang<br>• Mindestens ein Großbuchstabe (A-Z)<br>• Mindestens ein Kleinbuchstabe (a-z)<br>• Mindestens eine Zahl (0-9)<br>• Mindestens ein Sonderzeichen (!@#$%^&* etc.)<br>• Nicht zu ähnlich zu Ihren persönlichen Daten')
    )
    password2 = forms.CharField(
        max_length=150, 
        required=True, 
        label='Passwort wiederholen',
        help_text=_('Bitte geben Sie das Passwort erneut ein.')
    )
    
    def __init__(self, *args, **kwargs):
        self.org = kwargs.pop('org', None)
        super().__init__(*args, **kwargs)
        
        self.fields['first_name'].widget = forms.TextInput(attrs={'class': 'form-control', 'autocomplete': 'given-name'})
        self.fields['last_name'].widget = forms.TextInput(attrs={'class': 'form-control', 'autocomplete': 'family-name'})
        self.fields['email'].widget = forms.TextInput(attrs={'class': 'form-control', 'autocomplete': 'email'})
        self.fields['password'].widget = forms.PasswordInput(attrs={'class': 'form-control', 'autocomplete': 'new-password'})
        self.fields['password2'].widget = forms.PasswordInput(attrs={'class': 'form-control', 'autocomplete': 'new-password'})
        
        # Add help text classes for styling
        for field in self.fields.values():
            if field.help_text:
                field.widget.attrs['class'] = field.widget.attrs.get('class', '') + ' mb-1'
                field.help_text = f'<small class="form-text text-muted">{field.help_text}</small>'
    
    def clean(self):            
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        password2 = cleaned_data.get('password2')
        email = cleaned_data.get('email')
        
        if password and password2 and password != password2:
            self.add_error('password', forms.ValidationError(_('Passwörter stimmen nicht überein.')))
            self.add_error('password2', forms.ValidationError(_('Passwörter stimmen nicht überein.')))

        # Create a temporary user for password validation
        if email and password:
            temp_user = get_user_model()(
                username=email,
                email=email,
                first_name=cleaned_data.get('first_name', ''),
                last_name=cleaned_data.get('last_name', '')
            )
            from django.contrib.auth.password_validation import validate_password
            try:
                validate_password(password, temp_user)
            except forms.ValidationError as e:
                self.add_error('password', e)

        return cleaned_data
    
    def save(self):
        user = User.objects.create_user(
            username=self.cleaned_data['email'],
            first_name=self.cleaned_data['first_name'],
            last_name=self.cleaned_data['last_name'],
            email=self.cleaned_data['email'],
            password=self.cleaned_data['password']
        )
        
        person_cluster = PersonCluster.objects.filter(view='B').first()
        custom_user, created = CustomUser.objects.get_or_create(
            org=self.org,
            user=user,
            person_cluster=person_cluster
        )
        
        bewerber, created = Bewerber.objects.get_or_create(
            user=user,
            org=self.org
        )
        return user, bewerber
       
        
        
class ApplicationAnswerForm(forms.ModelForm):
    class Meta:
        model = ApplicationAnswer
        fields = ['answer']
        
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        self.question = kwargs.pop('question', None)
        super().__init__(*args, **kwargs)
        
        # If the question has choices, create a select field
        if self.question.choices:
            choices = [('', '- auswählen -')]
            choices.extend([(choice.strip(), choice.strip()) for choice in self.question.choices.split(',')])
            self.fields['answer'].widget = forms.Select(
                choices=choices,
                attrs={'class': 'form-select form-select-lg'}
            )
        else:
            # Otherwise, use a textarea
            max_length = self.question.max_length
            if max_length:
                self.fields['answer'].widget = forms.Textarea(
                    attrs={
                        'class': 'form-control form-control-lg',
                        'rows': max_length//100,
                        'maxlength': max_length
                    }
                )
            else:
                self.fields['answer'].widget = forms.Textarea(
                    attrs={
                        'class': 'form-control form-control-lg',
                        'rows': 3
                    }
                )
    
    def clean(self):
        cleaned_data = super().clean()
        answer = cleaned_data.get('answer')
        if answer and not self.question.choices and len(answer) > self.question.max_length:
            raise forms.ValidationError(f'Answer is too long. Max length is {self.question.max_length} characters.')
        return cleaned_data
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.user = self.user
        instance.org = self.user.customuser.org
        instance.question = self.question
        instance.save()
        return instance
        
class ApplicationFileAnswerForm(forms.ModelForm):
    class Meta:
        model = ApplicationAnswerFile
        fields = ['file']
        
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        self.file_question = kwargs.pop('file_question', None)
        super().__init__(*args, **kwargs)
        
        self.fields['file'].required = True
        self.fields['file'].help_text = 'Erlaubte Dateiformate: ' + ', '.join(self.file_question.ALLOWED_EXTENSIONS)
        self.fields['file'].widget = forms.FileInput(attrs={'class': 'form-control', 'accept': ','.join(self.file_question.ALLOWED_EXTENSIONS)})
    
    def clean(self):
        cleaned_data = super().clean()
        file = cleaned_data.get('file')
        
        if file:
            # Check file size (max 5MB)
            if file.size > 5 * 1024 * 1024:
                raise forms.ValidationError('Die Datei ist zu groß. Maximale Größe: 5MB')
            
            # Check file extension
            ext = '.' + file.name.split('.')[-1].lower()
            if ext not in self.file_question.ALLOWED_EXTENSIONS:
                raise forms.ValidationError('Nicht unterstütztes Dateiformat. Erlaubte Formate: ' + ', '.join(self.file_question.ALLOWED_EXTENSIONS))
        
        return cleaned_data
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.user = self.user
        instance.org = self.user.customuser.org
        instance.file_question = self.file_question
        
        # Delete old file if exists
        if instance.pk:
            old_instance = ApplicationAnswerFile.objects.get(pk=instance.pk)
            if old_instance.file:
                old_instance.file.delete()
        
        if commit:
            instance.save()
        return instance
        
        
        
