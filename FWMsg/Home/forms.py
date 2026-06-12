from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from Global.models import Einsatzland2

from .models import OwnSigninUser

User = get_user_model()

# class PasswordResetForm(forms.Form):
#     email = forms.EmailField(label='Email')

class EmailAuthenticationForm(AuthenticationForm):
    """
    Custom authentication form that accepts either username or email address in the username field.
    """
    username = forms.CharField(
        label=_("Benutzername oder E-Mail"),
        widget=forms.TextInput(attrs={"autofocus": True, 'class': 'form-control rounded-3'}),
    )
    password = forms.CharField(
        label=_("Passwort"),
        strip=False,
        widget=forms.PasswordInput(attrs={'autocomplete': 'current-password', 'class': 'form-control rounded-3'}),
    )
    
    def clean(self):
        """
        Override the default clean method to skip the built-in authentication
        that happens in AuthenticationForm.
        """
        username = self.cleaned_data.get('username')
        password = self.cleaned_data.get('password')
        
        if username is None or password is None:
            raise forms.ValidationError(
                self.error_messages['invalid_login'],
                code='invalid_login',
            )
        
        # We skip the authentication here and let the view handle it
        return self.cleaned_data

class FirstLoginForm(forms.Form):
    username = forms.CharField(
        label=_('Benutzername oder E-Mail'),
        widget=forms.TextInput(attrs={'class': 'form-control rounded-3', 'placeholder': _('Benutzername'), 'autocomplete': 'username'})
    )
    einmalpasswort = forms.CharField(
        label=_('Einmalpasswort'),
        widget=forms.TextInput(attrs={'class': 'form-control rounded-3', 'placeholder': _('Einmalpasswort'), 'autocomplete': 'one-time-password'})
    )
    password = forms.CharField(
        label=_('Neues Passwort'),
        widget=forms.PasswordInput(attrs={'class': 'form-control rounded-3', 'placeholder': _('Neues Passwort'), 'autocomplete': 'new-password'}),
        help_text=_('Ihr Passwort muss folgende Anforderungen erfüllen:<br>• Mindestens 8 Zeichen lang<br>• Mindestens ein Großbuchstabe (A-Z)<br>• Mindestens ein Kleinbuchstabe (a-z)<br>• Mindestens eine Zahl (0-9)<br>• Mindestens ein Sonderzeichen (!@#$%^&* etc.)<br>• Nicht zu ähnlich zu Ihren persönlichen Daten')
    )
    password_repeat = forms.CharField(
        label=_('Neues Passwort wiederholen'),
        widget=forms.PasswordInput(attrs={'class': 'form-control rounded-3', 'placeholder': _('Neues Passwort wiederholen'), 'autocomplete': 'new-password'})
    )

    def clean(self):
        cleaned_data = super().clean()
        username = cleaned_data.get('username')
        password = cleaned_data.get('password')
        password_repeat = cleaned_data.get('password_repeat')

        if password and password_repeat and password != password_repeat:
            raise ValidationError(_('Passwörter stimmen nicht überein.'))

        # Get the user for password validation
        if username and password:
            try:
                user = get_user_model().objects.get(username=username)
                from django.contrib.auth.password_validation import validate_password
                try:
                    validate_password(password, user)
                except ValidationError as e:
                    self.add_error('password', e)
            except get_user_model().DoesNotExist:
                pass  # Username validation will be handled elsewhere

        return cleaned_data


class OwnSigninForm(forms.ModelForm):
    class Meta:
        model = OwnSigninUser
        fields = ['first_name', 'last_name', 'email', 'land']
        widgets = {
            'first_name': forms.TextInput(attrs={
                'class': 'form-control rounded-3',
                'autocomplete': 'given-name',
            }),
            'last_name': forms.TextInput(attrs={
                'class': 'form-control rounded-3',
                'autocomplete': 'family-name',
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-control rounded-3',
                'autocomplete': 'email',
            }),
            'land': forms.Select(attrs={
                'class': 'form-select rounded-3',
            }),
        }

    def __init__(self, org, person_cluster=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.org = org
        self.person_cluster = person_cluster
        if person_cluster and person_cluster.view == 'B':
            del self.fields['land']
        elif 'land' in self.fields:
            self.fields['land'].queryset = Einsatzland2.objects.filter(org=org)
            self.fields['land'].empty_label = _('Land auswählen')

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if not email:
            return email

        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError(_('Ein Benutzer mit dieser E-Mail-Adresse existiert bereits.'))

        pending = OwnSigninUser.objects.filter(org=self.org, email__iexact=email)
        if self.instance.pk:
            pending = pending.exclude(pk=self.instance.pk)
        if pending.exists():
            raise ValidationError(_('Für diese E-Mail-Adresse liegt bereits eine Registrierungsanfrage vor.'))

        return email

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.org = self.org
        instance.person_cluster = self.person_cluster
        if commit:
            instance.save()
        return instance
