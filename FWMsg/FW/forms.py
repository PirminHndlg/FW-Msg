from django import forms
from .models import Bilder, BilderGallery


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
        model = Bilder
        fields = ['titel', 'beschreibung']
        widgets = {
            'beschreibung': forms.Textarea(attrs={'rows': 3}),
        }


class BilderGalleryForm(forms.ModelForm):
    class Meta:
        model = BilderGallery
        fields = ['image']
        widgets = {
            'image': MultipleFileInput(),
        }
