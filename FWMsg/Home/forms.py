from django import forms


class PasswordResetForm(forms.Form):
    username = forms.CharField(label='Username')
    email = forms.EmailField(label='Email')