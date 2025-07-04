from django import forms
from BW.models import Bewerber
from django.contrib.auth.models import User

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
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email']
        widgets = {
            'first_name': forms.TextInput(attrs={'placeholder': 'Maxi'}),
            'last_name': forms.TextInput(attrs={'placeholder': 'Muster'}),
            'email': forms.EmailInput(attrs={'placeholder': 'mm@mail.de'})
        }

    def __init__(self, *args, **kwargs):
        initial = kwargs.get('initial', {})
        # You can set default initial values here if needed
        super().__init__(*args, **kwargs)
