from django import forms
from BW.models import Bewerber
from django.contrib.auth.models import User
from .models import Seminar, Einheit, Frage, Fragekategorie

class WishForm(forms.ModelForm):
    class Meta:
        model = Bewerber
        fields = ['first_wish', 'second_wish', 'third_wish', 'no_wish']
        widgets = {
            'first_wish': forms.TextInput(attrs={'placeholder': 'Land 1'}),
            'second_wish': forms.TextInput(attrs={'placeholder': 'Land 2'}),
            'third_wish': forms.TextInput(attrs={'placeholder': 'Land 3'}),
            'no_wish': forms.TextInput(attrs={'placeholder': 'Nicht in dieses Land'}),
        }

    def __init__(self, *args, **kwargs):
        initial = kwargs.get('initial', {})
        # You can set default initial values here if needed
        super().__init__(*args, **kwargs)


class BewerterForm(forms.ModelForm):
    geburtsdatum = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'form-control',
            'placeholder': 'TT.MM.JJJJ'
        }),
        label='Geburtsdatum'
    )
    
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email']
        widgets = {
            'first_name': forms.TextInput(attrs={
                'placeholder': 'Maxi',
                'class': 'form-control'
            }),
            'last_name': forms.TextInput(attrs={
                'placeholder': 'Muster',
                'class': 'form-control'
            }),
            'email': forms.EmailInput(attrs={
                'placeholder': 'mm@mail.de',
                'class': 'form-control'
            })
        }
        labels = {
            'first_name': 'Vorname',
            'last_name': 'Nachname',
            'email': 'E-Mail',
        }

    def __init__(self, *args, **kwargs):
        # Extract the user instance to get the geburtsdatum from CustomUser
        user_instance = kwargs.get('instance')
        initial = kwargs.get('initial', {})
        
        # If we have a user instance, get the geburtsdatum from CustomUser
        if user_instance and hasattr(user_instance, 'customuser'):
            initial['geburtsdatum'] = user_instance.customuser.geburtsdatum
            kwargs['initial'] = initial

        super().__init__(*args, **kwargs)

        # Set label and required attribute for geburtsdatum field after super().__init__
        if user_instance and hasattr(user_instance, 'person_cluster') and hasattr(self.fields.get('geburtsdatum'), 'label'):
            if user_instance.role == 'E':
                self.fields['geburtsdatum'].label = 'Geburtsdatum'
                self.fields['geburtsdatum'].required = True
            else:
                self.fields['geburtsdatum'].label = 'Geburtsdatum (optional)'
                self.fields['geburtsdatum'].required = False

    def save(self, commit=True):
        user = super().save(commit=commit)
        
        if commit:
            # Save the geburtsdatum to the CustomUser model
            if hasattr(user, 'customuser'):
                user.customuser.geburtsdatum = self.cleaned_data.get('geburtsdatum')
                user.customuser.save()
        
        return user


class SeminarForm(forms.ModelForm):
    class Meta:
        model = Seminar
        fields = ['name', 'description', 'seminar_start', 'seminar_end', 'deadline_start', 'deadline_end']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'z.B. Einführungsseminar 2024',
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'placeholder': 'Beschreibung des Seminars',
                'rows': 3
            }),
            'seminar_start': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }, format='%Y-%m-%d'),
            'seminar_end': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }, format='%Y-%m-%d'),
            'deadline_start': forms.DateTimeInput(attrs={
                'class': 'form-control',
                'type': 'datetime-local'
            }, format='%Y-%m-%dT%H:%M'),
            'deadline_end': forms.DateTimeInput(attrs={
                'class': 'form-control',
                'type': 'datetime-local'
            }, format='%Y-%m-%dT%H:%M'),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Set input formats to match HTML5 inputs
        if self.instance and self.instance.pk:
            if self.instance.seminar_start:
                self.initial['seminar_start'] = self.instance.seminar_start.strftime('%Y-%m-%d')
            if self.instance.seminar_end:
                self.initial['seminar_end'] = self.instance.seminar_end.strftime('%Y-%m-%d')
            if self.instance.deadline_start:
                self.initial['deadline_start'] = self.instance.deadline_start.strftime('%Y-%m-%dT%H:%M')
            if self.instance.deadline_end:
                self.initial['deadline_end'] = self.instance.deadline_end.strftime('%Y-%m-%dT%H:%M')


class EinheitForm(forms.ModelForm):
    class Meta:
        model = Einheit
        fields = ['name', 'short_name']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Name der Einheit'
            }),
            'short_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Kurzname (optional)'
            }),
        }
        labels = {
            'name': 'Name',
            'short_name': 'Kurzname',
        }


class FragekategorieForm(forms.ModelForm):
    class Meta:
        model = Fragekategorie
        fields = ['name', 'short_name']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Name der Kategorie'
            }),
            'short_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Kurzname (optional)'
            }),
        }
        labels = {
            'name': 'Name',
            'short_name': 'Kurzname',
        }


class FrageForm(forms.ModelForm):
    class Meta:
        model = Frage
        fields = ['text', 'explanation', 'kategorie', 'min', 'max']
        widgets = {
            'text': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Frage Text'
            }),
            'explanation': forms.Textarea(attrs={
                'class': 'form-control',
                'placeholder': 'Erklärung (optional)',
                'rows': 2
            }),
            'kategorie': forms.Select(attrs={
                'class': 'form-select'
            }),
            'min': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 1,
                'max': 10
            }),
            'max': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 1,
                'max': 10
            }),
        }
        labels = {
            'text': 'Frage',
            'explanation': 'Erklärung',
            'kategorie': 'Kategorie',
            'min': 'Minimum Wert',
            'max': 'Maximum Wert',
        }
        
    def __init__(self, *args, **kwargs):
        org = kwargs.pop('org', None)
        super().__init__(*args, **kwargs)
        if org:
            self.fields['kategorie'].queryset = Fragekategorie.objects.filter(org=org)
