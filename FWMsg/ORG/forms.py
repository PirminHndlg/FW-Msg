from django import forms
from django.db import models

from FW import models as FWmodels
from . import models as ORGmodels

class AddFreiwilligerForm(forms.ModelForm):
    class Meta:
        model = FWmodels.Freiwilliger
        fields = '__all__'
        exclude = ['user', 'org']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


class AddAufgabeForm(forms.ModelForm):
    class Meta:
        model = FWmodels.Aufgabe
        fields = '__all__'
        exclude = ['org']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

class AddAufgabenprofilForm(forms.ModelForm):
    class Meta:
        model = FWmodels.Aufgabenprofil
        fields = '__all__'
        exclude = ['org']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


class AddFreiwilligerAufgabenForm(forms.ModelForm):
    class Meta:
        model = FWmodels.FreiwilligerAufgaben
        fields = '__all__'
        exclude = ['org']
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if 'freiwilliger' in self.fields:
            self.fields['freiwilliger'].disabled = True
        if 'aufgabe' in self.fields:
            self.fields['aufgabe'].disabled = True


class AddKirchenzugehoerigkeitForm(forms.ModelForm):
    class Meta:
        model = FWmodels.Kirchenzugehoerigkeit
        fields = '__all__'
        exclude = ['org']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

class AddEntsendeformForm(forms.ModelForm):
    class Meta:
        model = FWmodels.Entsendeform
        fields = '__all__'
        exclude = ['org']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


class AddEinsatzlandForm(forms.ModelForm):
    class Meta:
        model = FWmodels.Einsatzland
        fields = '__all__'
        exclude = ['org']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

class AddEinsatzstelleForm(forms.ModelForm):
    class Meta:
        model = FWmodels.Einsatzstelle
        fields = '__all__'
        exclude = ['org']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


class AddJahrgangForm(forms.ModelForm):
    class Meta:
        model = FWmodels.Jahrgang
        fields = '__all__'
        exclude = ['org']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


class AddNotfallkontaktForm(forms.ModelForm):
    class Meta:
        model = FWmodels.Notfallkontakt
        fields = '__all__'
        exclude = ['org']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


# Define which fields should be filterable for each model
filterable_fields = {
    FWmodels.Freiwilliger: ['jahrgang', 'einsatzland', 'entsendeform', 'kirchenzugehoerigkeit'],
    FWmodels.Aufgabe: ['faellig_art', 'mitupload'],
    FWmodels.Einsatzstelle: ['einsatzland'],
    FWmodels.Notfallkontakt: ['freiwilliger'],
    FWmodels.FreiwilligerAufgaben: ['freiwilliger', 'aufgabe', 'erledigt'],
    # FWmodels.Aufgabenprofil: ['aufgaben__aufgabe'],
}

class FilterForm(forms.Form):    
    def __init__(self, model_class, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Get the list of filterable fields for this model
        allowed_fields = filterable_fields.get(model_class, [])
        
        # Add filter fields based on model fields, but only for allowed fields
        for field in model_class._meta.fields:
            if field.name not in allowed_fields:
                continue
                
            if isinstance(field, (models.CharField, models.TextField)):
                self.fields[f'filter_{field.name}'] = forms.CharField(
                    required=False,
                    label=field.verbose_name,
                    widget=forms.TextInput(attrs={'class': 'form-control'})
                )
            elif isinstance(field, models.BooleanField):
                self.fields[f'filter_{field.name}'] = forms.ChoiceField(
                    required=False,
                    label=field.verbose_name,
                    choices=[('', '---'), ('true', 'Yes'), ('false', 'No')],
                    widget=forms.Select(attrs={'class': 'form-control'})
                )
            elif isinstance(field, models.DateField):
                self.fields[f'filter_{field.name}_from'] = forms.DateField(
                    required=False,
                    label=f'{field.verbose_name} from',
                    widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'})
                )
                self.fields[f'filter_{field.name}_to'] = forms.DateField(
                    required=False,
                    label=f'{field.verbose_name} to',
                    widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'})
                )
            elif isinstance(field, models.ForeignKey):
                self.fields[f'filter_{field.name}'] = forms.ModelChoiceField(
                    required=False,
                    queryset=field.related_model.objects.all(),
                    label=field.verbose_name,
                    widget=forms.Select(attrs={'class': 'form-control'})
                )

model_to_form_mapping = {
    FWmodels.Einsatzland: AddEinsatzlandForm,
    FWmodels.Einsatzstelle: AddEinsatzstelleForm,
    FWmodels.Freiwilliger: AddFreiwilligerForm,
    FWmodels.Aufgabe: AddAufgabeForm,
    FWmodels.Aufgabenprofil: AddAufgabenprofilForm,
    FWmodels.Jahrgang: AddJahrgangForm,
    FWmodels.Kirchenzugehoerigkeit: AddKirchenzugehoerigkeitForm,
    FWmodels.Notfallkontakt: AddNotfallkontaktForm,
    FWmodels.Entsendeform: AddEntsendeformForm,
    FWmodels.FreiwilligerAufgaben: AddFreiwilligerAufgabenForm
}
