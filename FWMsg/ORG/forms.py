import random
import string
from django import forms
from django.db import models
from django.contrib.auth.models import User
from django.forms import inlineformset_factory

from FW import models as FWmodels
from Global import models as Globalmodels
from . import models as ORGmodels

class OrgFormMixin:
    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
        if self.request and self.request.user.org:
            # Filter all ForeignKey fields by organization
            for field_name, field in self.fields.items():
                if isinstance(field, forms.ModelChoiceField):
                    related_model = field.queryset.model
                    if related_model == User:
                        field.queryset = field.queryset.filter(customuser__org=self.request.user.org)
                    elif hasattr(related_model, 'org'):
                        field.queryset = field.queryset.filter(org=self.request.user.org)


class AddFreiwilligerForm(OrgFormMixin, forms.ModelForm):
    class Meta:
        model = FWmodels.Freiwilliger
        fields = '__all__'
        exclude = ['user', 'org']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        date_field = forms.DateField(
            widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            required=False
        )
        self.fields['geburtsdatum'] = date_field
        self.fields['start_geplant'] = date_field
        self.fields['start_real'] = date_field
        self.fields['ende_geplant'] = date_field
        self.fields['ende_real'] = date_field



class AddAufgabeForm(OrgFormMixin, forms.ModelForm):
    class Meta:
        model = FWmodels.Aufgabe
        fields = '__all__'
        exclude = ['org']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Remove request from kwargs before passing to formset
        formset_kwargs = kwargs.copy()
        formset_kwargs.pop('request', None)
        self.zwischenschritte = AufgabeZwischenschritteFormSet(*args, **formset_kwargs)
        

    def is_valid(self):
        return super().is_valid() and self.zwischenschritte.is_valid()

    def save(self, commit=True):
        instance = super().save(commit=commit)
        if commit:
            self.zwischenschritte.instance = instance
            self.zwischenschritte.org = self.request.user.org
            self.zwischenschritte.save()
        return instance

# Create the formset for AufgabeZwischenschritte
AufgabeZwischenschritteFormSet = inlineformset_factory(
    FWmodels.Aufgabe,
    FWmodels.AufgabeZwischenschritte,
    fields=['name', 'beschreibung'],
    extra=0,
    can_delete=True,
    widgets={
        'beschreibung': forms.Textarea(attrs={'rows': 4}),
    }
)


class AddAufgabenprofilForm(OrgFormMixin, forms.ModelForm):
    class Meta:
        model = FWmodels.Aufgabenprofil
        fields = '__all__'
        exclude = ['org']


class AddFreiwilligerAufgabenForm(OrgFormMixin, forms.ModelForm):
    class Meta:
        model = FWmodels.FreiwilligerAufgaben
        fields = ['freiwilliger', 'aufgabe', 'personalised_description', 'faellig', 'wiederholung', 'wiederholung_ende', 'file', 'benachrichtigung_cc']
        exclude = ['org']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        date_field = forms.DateField(
            widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            required=False
        )
        self.fields['faellig'] = date_field
        self.fields['wiederholung_ende'] = date_field

        self.fields['freiwilliger'].widget = forms.Select(attrs={'class': 'form-control', 'disabled': True})
        self.fields['freiwilliger'].queryset = FWmodels.Freiwilliger.objects.filter(org=self.request.user.org)

        self.fields['aufgabe'].widget = forms.Select(attrs={'class': 'form-control', 'disabled': True})
        self.fields['aufgabe'].queryset = FWmodels.Aufgabe.objects.filter(org=self.request.user.org)

        self.fields['personalised_description'].widget = forms.Textarea(attrs={'rows': 2})


class AddKirchenzugehoerigkeitForm(OrgFormMixin, forms.ModelForm):
    class Meta:
        model = FWmodels.Kirchenzugehoerigkeit
        fields = '__all__'
        exclude = ['org']


class AddEntsendeformForm(OrgFormMixin, forms.ModelForm):
    class Meta:
        model = FWmodels.Entsendeform
        fields = '__all__'
        exclude = ['org']


class AddEinsatzlandForm(OrgFormMixin, forms.ModelForm):
    class Meta:
        model = FWmodels.Einsatzland
        fields = '__all__'
        exclude = ['org']


class AddEinsatzstelleForm(OrgFormMixin, forms.ModelForm):
    class Meta:
        model = FWmodels.Einsatzstelle
        fields = '__all__'
        exclude = ['org']


class AddJahrgangForm(OrgFormMixin, forms.ModelForm):
    class Meta:
        model = FWmodels.Jahrgang
        fields = '__all__'
        exclude = ['org']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        date_field = forms.DateField(
            widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            required=False
        )
        self.fields['start'] = date_field
        self.fields['ende'] = date_field

class AddNotfallkontaktForm(OrgFormMixin, forms.ModelForm):
    class Meta:
        model = FWmodels.Notfallkontakt
        fields = '__all__'
        exclude = ['org']


class AddUserForm(OrgFormMixin, forms.ModelForm):
    username = forms.CharField(max_length=150, required=False, label='Username', help_text='Wird automatisch mit Vornamen erzeugt, wenn leer')
    first_name = forms.CharField(max_length=150, required=False, label='First Name')
    last_name = forms.CharField(max_length=150, required=False, label='Last Name')
    email = forms.EmailField(required=False, label='Email')

    class Meta:
        model = Globalmodels.CustomUser
        fields = ['username', 'first_name', 'last_name', 'email', 'role', 'einmalpasswort', 'profil_picture']
        exclude = ['org']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # If we're editing an existing instance, populate the user fields
        if self.instance and self.instance.pk and hasattr(self.instance, 'user'):
            self.fields['username'].initial = self.instance.user.username
            self.fields['first_name'].initial = self.instance.user.first_name
            self.fields['last_name'].initial = self.instance.user.last_name
            self.fields['email'].initial = self.instance.user.email

    def save(self, commit=True):
        custom_user = super().save(commit=False)
        
        if custom_user.pk:  # If editing existing user
            user = custom_user.user
            user.email = self.cleaned_data['email']
            user.first_name = self.cleaned_data['first_name']
            user.last_name = self.cleaned_data['last_name']
            user.username = self.cleaned_data['username'] or user.username
            user.save()
        else:  # If creating new user
            username = self.cleaned_data['username'] or self.cleaned_data['first_name'].split(' ')[0]
            
            # Ensure unique username
            while User.objects.filter(username=username).exists():
                username = username + str(random.randint(1, 9))
            
            # Create User instance
            user = User.objects.create_user(
                username=username,
                email=self.cleaned_data['email'],
                password=''.join(random.choices(string.ascii_letters + string.digits, k=10)),
                first_name=self.cleaned_data['first_name'],
                last_name=self.cleaned_data['last_name']
            )
            custom_user.user = user
        
        if commit:
            custom_user.save()
            self.save_m2m()
        
        return custom_user


# Define which fields should be filterable for each model
filterable_fields = {
    FWmodels.Freiwilliger: ['jahrgang', 'einsatzland', 'entsendeform', 'kirchenzugehoerigkeit'],
    FWmodels.Aufgabe: ['faellig_art', 'mitupload'],
    FWmodels.Einsatzstelle: ['einsatzland'],
    FWmodels.Notfallkontakt: ['freiwilliger'],
    FWmodels.FreiwilligerAufgaben: ['freiwilliger', 'aufgabe', 'erledigt'],
    Globalmodels.CustomUser: ['role'],
    # FWmodels.Aufgabenprofil: ['aufgaben__aufgabe'],
}

class FilterForm(forms.Form):    
    def __init__(self, model_class, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
        
        # Get the list of filterable fields for this model
        allowed_fields = filterable_fields.get(model_class, [])
        
        # Add filter fields based on model fields, but only for allowed fields
        for field in model_class._meta.fields:
            if field.name not in allowed_fields:
                continue
                
            if isinstance(field, (models.CharField, models.TextField)):
                if field.choices:
                    self.fields[f'filter_{field.name}'] = forms.ChoiceField(
                        required=False,
                        label=field.verbose_name,
                        choices=field.choices,
                        widget=forms.Select(attrs={'class': 'form-control'})
                    )
                else:
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
                queryset = field.related_model.objects.all()
                # Filter by organization if model has org field
                if self.request and hasattr(field.related_model, 'org'):
                    queryset = queryset.filter(org=self.request.user.org)
                self.fields[f'filter_{field.name}'] = forms.ModelChoiceField(
                    required=False,
                    queryset=queryset,
                    label=field.verbose_name,
                    widget=forms.Select(attrs={'class': 'form-control'})
                )


class AddReferentenForm(OrgFormMixin, forms.ModelForm):
    class Meta:
        model = ORGmodels.Referenten
        fields = '__all__'
        exclude = ['org', 'user']

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
    FWmodels.FreiwilligerAufgaben: AddFreiwilligerAufgabenForm,
    ORGmodels.Referenten: AddReferentenForm,
    Globalmodels.CustomUser: AddUserForm
}
