from django import forms
from django.utils.log import logging
from Global.models import Bilder2, BilderGallery2, ProfilUser2
from django.utils.translation import gettext_lazy as _
from django.forms.widgets import HiddenInput
from django.utils import timezone
import uuid

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
    submission_key = forms.UUIDField(widget=HiddenInput, required=False)
    
    class Meta:
        model = Bilder2
        fields = ['titel', 'beschreibung']
        widgets = {
            'beschreibung': forms.Textarea(attrs={'rows': 3}),
        }
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        self.org = kwargs.pop('org', None)
        super().__init__(*args, **kwargs)
        self.fields['titel'].widget.attrs.update({'class': 'form-control', 'placeholder': _('Bildtitel')})
        self.fields['beschreibung'].widget.attrs.update({'class': 'form-control', 'placeholder': _('Beschreibung (optional)')})
        self.fields['submission_key'].required = False
    
    def save(self, images=None, commit=True):
        if not self.is_valid():
            raise ValueError('Form is not valid')
        
        key = self.cleaned_data.get('submission_key') or uuid.uuid4()
        
        # Idempotency by submission_key scoped to org
        existing = Bilder2.objects.filter(submission_key=key, org=self.org).first()
        if existing:
            # Update existing record
            existing.titel = self.cleaned_data['titel']
            existing.beschreibung = self.cleaned_data.get('beschreibung', '')
            existing.date_updated = timezone.now()
            existing.save()
            # Add new images if provided
            if images:
                for image in images:
                    try:
                        BilderGallery2.objects.create(
                            org=self.org,
                            bilder=existing,
                            image=image
                        )
                    except Exception as e:
                        logging.error(f"Error creating BilderGallery2: {e}")
                        
            if BilderGallery2.objects.filter(bilder=existing).count() == 0:
                existing.delete()
                return None, False
            
            return existing, False
        
        # Create new Bilder2 object
        obj = Bilder2.objects.create(
            user=self.user,
            org=self.org,
            titel=self.cleaned_data['titel'],
            beschreibung=self.cleaned_data.get('beschreibung', ''),
            submission_key=key
        )
        # Add images if provided
        if images:
            for image in images:
                try:
                    BilderGallery2.objects.create(
                        org=self.org,
                        bilder=obj,
                        image=image
                    )
                except Exception as e:
                    logging.error(f"Error creating BilderGallery2: {e}")
                    
        if BilderGallery2.objects.filter(bilder=obj).count() == 0:
            obj.delete()
            return None, False
        
        return obj, True


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
            'attribut': forms.TextInput(attrs={'placeholder': _('Z.B. Instagram'), 'class': 'form-control'}),
            'value': forms.TextInput(attrs={'placeholder': '@luisaneubauer', 'class': 'form-control'}),
        }
