from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.utils.translation import gettext_lazy as _


class PasswordResetForm(forms.Form):
    username = forms.CharField(label='Username')
    email = forms.EmailField(label='Email')

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