from django import forms
from ORG.models import Organisation

class OrganisationForm(forms.ModelForm):
    class Meta:
        model = Organisation
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Make logo field optional if we're editing an existing organization
        if self.instance and self.instance.pk:
            self.fields['logo'].required = False

    def save(self, commit=True):
        instance = super().save(commit=False)
        # If no new file is uploaded and we're editing an existing organization,
        # keep the existing logo
        if not self.cleaned_data.get('logo') and self.instance and self.instance.pk:
            instance.logo = self.instance.logo
        if commit:
            instance.save()
        return instance


