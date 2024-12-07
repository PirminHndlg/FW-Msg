from django import forms

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



model_to_form_mapping = {
    FWmodels.Einsatzland: AddEinsatzlandForm,
    FWmodels.Einsatzstelle: AddEinsatzstelleForm,
    FWmodels.Freiwilliger: AddFreiwilligerForm,
    FWmodels.Aufgabe: AddAufgabeForm,
    FWmodels.Aufgabenprofil: AddAufgabenprofilForm,
    FWmodels.Jahrgang: AddJahrgangForm,
    FWmodels.Kirchenzugehoerigkeit: AddKirchenzugehoerigkeitForm,
    FWmodels.Notfallkontakt: AddNotfallkontaktForm,
    FWmodels.Entsendeform: AddEntsendeformForm
}
