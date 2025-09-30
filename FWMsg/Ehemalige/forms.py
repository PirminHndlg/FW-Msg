from django import forms
from .models import Ehemalige

class EhemaligeForm(forms.ModelForm):
    class Meta:
        model = Ehemalige
        fields = ['land']