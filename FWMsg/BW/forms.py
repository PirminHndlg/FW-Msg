from datetime import datetime
import random
import string
from django import forms
from django.db import IntegrityError, models
from django.contrib.auth.models import User
from Global.models import CustomUser, PersonCluster
from .models import ApplicationQuestion, ApplicationAnswer, Bewerber, ApplicationAnswerFile


class CreateAccountForm(forms.Form):
    first_name = forms.CharField(max_length=150, required=True, label='Vorname')
    last_name = forms.CharField(max_length=150, required=True, label='Nachname')
    email = forms.EmailField(required=True, label='Email')
    password = forms.CharField(max_length=150, required=True, label='Password')
    password2 = forms.CharField(max_length=150, required=True, label='Password2')
    
    def __init__(self, *args, **kwargs):
        self.org = kwargs.pop('org', None)
        super().__init__(*args, **kwargs)
        
        self.fields['first_name'].widget = forms.TextInput(attrs={'class': 'form-control', 'autocomplete': 'given-name'})
        self.fields['last_name'].widget = forms.TextInput(attrs={'class': 'form-control', 'autocomplete': 'family-name'})
        self.fields['email'].widget = forms.TextInput(attrs={'class': 'form-control', 'autocomplete': 'email'})
        self.fields['password'].widget = forms.PasswordInput(attrs={'class': 'form-control', 'autocomplete': 'new-password'})
        self.fields['password2'].widget = forms.PasswordInput(attrs={'class': 'form-control', 'autocomplete': 'new-password'})
    
    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        password2 = cleaned_data.get('password2')
        if password != password2:
            raise forms.ValidationError('Passwords do not match')
        return cleaned_data
    
    def save(self):
        user = User.objects.create_user(
            username=self.cleaned_data['email'],
            email=self.cleaned_data['email'],
            password=self.cleaned_data['password']
        )
        
        person_cluster = PersonCluster.objects.filter(view='B').first()
        custom_user = CustomUser.objects.create(
            org=self.org,
            user=user,
            person_cluster=person_cluster
        )
        
        Bewerber.objects.create(
            user=user,
            org=self.org
        )
        return user
       
        
        
class ApplicationAnswerForm(forms.ModelForm):
    class Meta:
        model = ApplicationAnswer
        fields = ['answer']
        
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        self.question = kwargs.pop('question', None)
        super().__init__(*args, **kwargs)
        max_length = self.question.max_length
        if max_length:
            self.fields['answer'].widget = forms.Textarea(attrs={'class': 'form-control', 'rows': max_length//50, 'maxlength': max_length})
        else:
            self.fields['answer'].widget = forms.Textarea(attrs={'class': 'form-control', 'rows': 3})
    
    def clean(self):
        cleaned_data = super().clean()
        answer = cleaned_data.get('answer')
        if answer and len(answer) > self.question.max_length:
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
        self.fields['file'].help_text = 'Erlaubte Dateiformate: PDF, DOC, DOCX, TXT'
        self.fields['file'].widget = forms.FileInput(attrs={'class': 'form-control'})
    
    def clean(self):
        cleaned_data = super().clean()
        file = cleaned_data.get('file')
        
        if file:
            # Check file size (max 5MB)
            if file.size > 5 * 1024 * 1024:
                raise forms.ValidationError('Die Datei ist zu groß. Maximale Größe: 5MB')
            
            # Check file extension
            ext = file.name.split('.')[-1].lower()
            if ext not in ['pdf', 'doc', 'docx', 'txt']:
                raise forms.ValidationError('Nicht unterstütztes Dateiformat. Erlaubte Formate: PDF, DOC, DOCX, TXT')
        
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
        
        
        
