from django import forms
from Global.models import Bilder2, BilderGallery2, ProfilUser2


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("widget", MultipleFileInput())
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        single_file_clean = super().clean
        if isinstance(data, (list, tuple)):
            result = [single_file_clean(d, initial) for d in data]
        else:
            result = [single_file_clean(data, initial)]
        return result


class BilderForm(forms.ModelForm):
    class Meta:
        model = Bilder2
        fields = ['titel', 'beschreibung']
        widgets = {
            'beschreibung': forms.Textarea(attrs={'rows': 3}),
        }


class BilderGalleryForm(forms.ModelForm):
    class Meta:
        model = BilderGallery2
        fields = ['image']
        widgets = {
            'image': MultipleFileInput(),
        }


class ProfilUserForm(forms.ModelForm):
    class Meta:
        model = ProfilUser2
        fields = ['attribut', 'value']
        widgets = {
            'attribut': forms.TextInput(attrs={'placeholder': 'Attribut'}),
            'value': forms.TextInput(attrs={'placeholder': 'Wert'}),
        }
