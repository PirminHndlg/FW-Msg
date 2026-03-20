from django import forms
from django.contrib.auth.models import User
from .models import ChatDirect, ChatGroup


class ChatDirectForm(forms.ModelForm):
    class Meta:
        model = ChatDirect
        fields = ['users']

    def __init__(self, *args, org=None, current_user=None, **kwargs):
        super().__init__(*args, **kwargs)
        qs = User.objects.filter(customuser__org=org).order_by('customuser__person_cluster', 'first_name', 'last_name')
        if current_user and current_user.id:
            qs = qs.exclude(pk=current_user.id)
        qs = qs.exclude(customuser__person_cluster__view='B')
        qs = qs.select_related('customuser')
        self.fields['users'].queryset = qs
        self.fields['users'].label = 'Benutzer:in'
        self.fields['users'].widget.attrs.update({'class': 'form-select'})


class ChatGroupForm(forms.ModelForm):
    class Meta:
        model = ChatGroup
        fields = ['name', 'users']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, org=None, current_user=None, **kwargs):
        super().__init__(*args, **kwargs)
        qs = User.objects.filter(customuser__org=org).order_by('customuser__person_cluster', 'first_name', 'last_name')
        if current_user and current_user.id:
            qs = qs.exclude(pk=current_user.id)
        qs = qs.exclude(customuser__person_cluster__view='B')
        qs = qs.select_related('customuser')
        self.fields['users'].queryset = qs
        self.fields['users'].label = 'Mitglieder'
        self.fields['users'].widget.attrs.update({'class': 'form-select'})
        self.fields['name'].label = 'Gruppenname'


class SendDirectMessageForm(forms.Form):
    message = forms.CharField(
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nachricht schreiben…', 'autocomplete': 'off'}),
        label='',
    )


class SendGroupMessageForm(forms.Form):
    message = forms.CharField(
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nachricht schreiben…', 'autocomplete': 'off'}),
        label='',
    )
