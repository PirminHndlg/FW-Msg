from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _


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
        widget=forms.TextInput(attrs={'class': 'form-control rounded-3', 'placeholder': _('Benutzername')})
    )
    einmalpasswort = forms.CharField(
        label=_('Einmalpasswort'),
        widget=forms.TextInput(attrs={'class': 'form-control rounded-3', 'placeholder': _('Einmalpasswort')})
    )
    password = forms.CharField(
        label=_('Neues Passwort'),
        widget=forms.PasswordInput(attrs={'class': 'form-control rounded-3', 'placeholder': _('Neues Passwort')}),
        help_text=_('Ihr Passwort muss folgende Anforderungen erfüllen:<br>• Mindestens 8 Zeichen lang<br>• Mindestens ein Großbuchstabe (A-Z)<br>• Mindestens ein Kleinbuchstabe (a-z)<br>• Mindestens eine Zahl (0-9)<br>• Mindestens ein Sonderzeichen (!@#$%^&* etc.)<br>• Nicht zu ähnlich zu Ihren persönlichen Daten')
    )
    password_repeat = forms.CharField(
        label=_('Neues Passwort wiederholen'),
        widget=forms.PasswordInput(attrs={'class': 'form-control rounded-3', 'placeholder': _('Neues Passwort wiederholen')})
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