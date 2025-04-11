from datetime import datetime
import random
import string
from django import forms
from django.db import models
from django.contrib.auth.models import User
from django.forms import inlineformset_factory

from Global.models import (
    Attribute, Aufgabe2, 
    UserAufgaben, Post2, Bilder2, CustomUser,
    BilderGallery2, Ampel2, ProfilUser2, Notfallkontakt2, UserAttribute, 
    PersonCluster, Einsatzland2, Einsatzstelle2,
    AufgabeZwischenschritte2
)
from FW.models import Freiwilliger
from TEAM.models import Team


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


class AddAttributeForm(OrgFormMixin, forms.ModelForm):
    class Meta:
        model = Attribute
        fields = '__all__'
        exclude = ['org']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['person_cluster'].queryset = PersonCluster.objects.filter(org=self.request.user.org)


def add_customuser_fields(self, view):
    self.fields['first_name'] = forms.CharField(
        widget=forms.TextInput(attrs={'class': 'form-control'}),
        required=True,
        label='Vorname'
    )
    if self.instance and self.instance.pk:
        self.fields['first_name'].initial = self.instance.user.first_name

    self.fields['last_name'] = forms.CharField(
        widget=forms.TextInput(attrs={'class': 'form-control'}),
        required=True,
        label='Nachname'
    )
    if self.instance and self.instance.pk:
        self.fields['last_name'].initial = self.instance.user.last_name

    self.fields['email'] = forms.EmailField(
        widget=forms.EmailInput(attrs={'class': 'form-control'}),
        required=True,
        label='E-Mail'
    )
    if self.instance and self.instance.pk:
        self.fields['email'].initial = self.instance.user.email

    self.fields['person_cluster'] = forms.ModelChoiceField(
        queryset=PersonCluster.objects.filter(org=self.request.user.org, view=view),
        widget=forms.Select(attrs={'class': 'form-control'}),
        required=True,
        label='Person Cluster'
    )
    if self.instance and self.instance.pk:
        self.fields['person_cluster'].initial = self.instance.user.customuser.person_cluster


def add_person_cluster_field(self):
    person_cluster_typ = self.instance.user.customuser.person_cluster if self.instance and self.instance.pk else None
    if person_cluster_typ:
        attributes = Attribute.objects.filter(org=self.request.user.org, person_cluster=person_cluster_typ)
        for attribute in attributes:
            print(attribute.type)
            if attribute.type == 'T':
                self.fields[attribute.name] = forms.CharField(
                    widget=forms.TextInput(attrs={'class': 'form-control'}),
                    required=False
                )
            elif attribute.type == 'L':
                self.fields[attribute.name] = forms.CharField(
                    widget=forms.Textarea(attrs={'class': 'form-control'}),
                    required=False
                )
            elif attribute.type == 'N':
                self.fields[attribute.name] = forms.IntegerField(
                    widget=forms.NumberInput(attrs={'class': 'form-control'}),
                    required=False
                )
            elif attribute.type == 'E':
                self.fields[attribute.name] = forms.EmailField(
                    widget=forms.EmailInput(attrs={'class': 'form-control'}),
                    required=False
                )
            elif attribute.type == 'B':
                self.fields[attribute.name] = forms.BooleanField(
                    widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
                    required=False
                )
            elif attribute.type == 'F':
                self.fields[attribute.name] = forms.FileField(
                    widget=forms.FileInput(attrs={'class': 'form-control'}),
                    required=False
                )
            elif attribute.type == 'P':
                self.fields[attribute.name] = forms.CharField(
                    widget=forms.TextInput(attrs={'class': 'form-control'}),
                    required=False
                )
            elif attribute.type == 'D':
                self.fields[attribute.name] = forms.DateField(
                    widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
                    required=False
                )
            elif attribute.type == 'C':
                choices = [(x.strip(), x.strip()) for x in (attribute.value_for_choices or '').split(',') if x.strip()]
                choices.insert(0, ('', '---'))
                self.fields[attribute.name] = forms.ChoiceField(
                    widget=forms.Select(attrs={'class': 'form-control'}),
                    choices=choices,
                    required=False
                )

            
            freiwlliger_attribute = UserAttribute.objects.filter(user=self.instance.user, attribute=attribute).first()
            if freiwlliger_attribute:
                if attribute.type == 'B':
                    self.fields[attribute.name].initial = freiwlliger_attribute.value == 'True'
                elif attribute.type == 'D':
                    #format datestring to date
                    if freiwlliger_attribute.value:
                        try:
                            self.fields[attribute.name].initial = datetime.strptime(freiwlliger_attribute.value, '%Y-%m-%d').date()
                        except ValueError:
                            self.fields[attribute.name].initial = None
                    else:
                        self.fields[attribute.name].initial = None
                else:
                    self.fields[attribute.name].initial = freiwlliger_attribute.value


def save_and_create_customuser(self):
    base_username = self.cleaned_data['first_name'].split(' ')[0].lower()
    username = base_username
    counter = 1
    
    while User.objects.filter(username=username).exists():
        username = f"{base_username}{counter}"
        counter += 1

    self.instance.user = User.objects.create_user(
        username=username,
        email=self.cleaned_data['email'],
        first_name=self.cleaned_data['first_name'],
        last_name=self.cleaned_data['last_name']
    )
    self.instance.org = self.request.user.org

    self.instance.user.customuser = CustomUser.objects.create(
        user=self.instance.user,
        org=self.request.user.org,
        person_cluster=self.cleaned_data['person_cluster']
    )
    self.instance.user.customuser.save()
    self.instance.user.save()


def save_person_cluster_field(self):
    for attribute in Attribute.objects.filter(org=self.request.user.org, person_cluster=self.instance.user.customuser.person_cluster):
        freiwlliger_attribute, created = UserAttribute.objects.get_or_create(org=self.request.user.org, user=self.instance.user, attribute=attribute)
        if attribute.name in self.cleaned_data:
            freiwlliger_attribute.value = self.cleaned_data[attribute.name]
            freiwlliger_attribute.save()

class AddFreiwilligerForm(OrgFormMixin, forms.ModelForm):
    class Meta:
        model = Freiwilliger
        fields = '__all__'
        exclude = ['user', 'org']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        date_field = forms.DateField(
            widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            required=False
        )

        self.fields['start_geplant'] = date_field
        self.fields['start_real'] = date_field
        self.fields['ende_geplant'] = date_field
        self.fields['ende_real'] = date_field

        add_customuser_fields(self, 'F')

        self.fields['geburtsdatum'] = forms.DateField(
            widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            required=False
        )
        if self.instance and self.instance.pk:
            self.fields['geburtsdatum'].initial = self.instance.user.customuser.geburtsdatum
        
        order_fields = ['first_name', 'last_name', 'email', 'person_cluster', 'geburtsdatum']
        self.order_fields(order_fields)

        add_person_cluster_field(self)
                    
                
    def save(self, commit=True):
        if not self.instance.pk:
            save_and_create_customuser(self)
            self.instance.save()
        else:
            self.instance.user.customuser.person_cluster = self.cleaned_data['person_cluster']
            self.instance.user.customuser.save()

        instance = super().save(commit=commit)

        save_person_cluster_field(self)
        
        return instance



class AddAufgabeForm(OrgFormMixin, forms.ModelForm):
    class Meta:
        model = Aufgabe2
        fields = '__all__'
        exclude = ['org']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Remove request from kwargs before passing to formset
        formset_kwargs = kwargs.copy()
        formset_kwargs.pop('request', None)
        self.zwischenschritte = AufgabeZwischenschritteFormSet(*args, **formset_kwargs)

        self.fields['wiederholung_ende'] = forms.DateField(
            widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            required=False
        )

        self.fields['person_cluster'].queryset = PersonCluster.objects.filter(org=self.request.user.org)

    def is_valid(self):
        return super().is_valid() and self.zwischenschritte.is_valid()

    def save(self, commit=True):
        from ORG.views import get_person_cluster

        # self.instance.person_cluster = get_person_cluster(self.request)
        instance = super().save(commit=commit)
        if commit:
            self.zwischenschritte.instance = instance
            self.zwischenschritte.org = self.request.user.org
            self.zwischenschritte.save()
        return instance

# Create the formset for AufgabeZwischenschritte
AufgabeZwischenschritteFormSet = inlineformset_factory(
    Aufgabe2,
    AufgabeZwischenschritte2,
    fields=['name', 'beschreibung'],
    extra=0,
    can_delete=True,
    widgets={
        'beschreibung': forms.Textarea(attrs={'rows': 4}),
    }
)


class AddFreiwilligerAufgabenForm(OrgFormMixin, forms.ModelForm):
    user_display = forms.CharField(
        label='User',
        required=False,
        widget=forms.TextInput(attrs={'readonly': True, 'class': 'form-control-plaintext fw-bold row w-75 ms-3', 'style': 'display: inline-block;'})
    )
    aufgabe_display = forms.CharField(
        label='Aufgabe', 
        required=False,
        widget=forms.TextInput(attrs={'readonly': True, 'class': 'form-control-plaintext fw-bold row w-75 ms-3', 'style': 'display: inline-block;'})
    )

    class Meta:
        model = UserAufgaben
        fields = ['personalised_description', 'faellig', 'file', 'benachrichtigung_cc']
        exclude = ['org']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        date_field = forms.DateField(
            widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            required=False
        )
        self.fields['faellig'] = date_field

        self.fields['benachrichtigung_cc'].widget.attrs['placeholder'] = 'E-Mail-Adressen mit Komma getrennt'
        self.fields['benachrichtigung_cc'].help_text = 'Geben Sie hier E-Mail-Adressen ein, die eine Kopie der Benachrichtigungen erhalten sollen'

        # Hide the actual fields and set up display fields
        if self.instance and self.instance.pk:
            
            # Set initial values for display fields
            self.fields['user_display'].initial = str(self.instance.user.first_name) + ' ' + str(self.instance.user.last_name)
            self.fields['aufgabe_display'].initial = str(self.instance.aufgabe)

            # Reorder fields to show display fields first
            field_order = ['user_display', 'aufgabe_display', 'personalised_description', 
                          'faellig', 'file', 
                          'benachrichtigung_cc']
            self.order_fields(field_order)



class AddEinsatzlandForm(OrgFormMixin, forms.ModelForm):
    class Meta:
        model = Einsatzland2
        fields = '__all__'
        exclude = ['org']


class AddEinsatzstelleForm(OrgFormMixin, forms.ModelForm):
    class Meta:
        model = Einsatzstelle2
        fields = '__all__'
        exclude = ['org']


class AddNotfallkontaktForm(OrgFormMixin, forms.ModelForm):
    class Meta:
        model = Notfallkontakt2
        fields = '__all__'
        exclude = ['org', 'user']


class AddUserForm(OrgFormMixin, forms.ModelForm):
    username = forms.CharField(max_length=150, required=False, label='Username', help_text='Wird automatisch mit Vornamen erzeugt, wenn leer')
    first_name = forms.CharField(max_length=150, required=False, label='First Name')
    last_name = forms.CharField(max_length=150, required=False, label='Last Name')
    email = forms.EmailField(required=False, label='Email')

    class Meta:
        model = CustomUser
        fields = ['username', 'first_name', 'last_name', 'person_cluster', 'email', 'einmalpasswort', 'profil_picture']
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
    Freiwilliger: ['person_cluster', 'einsatzland', 'einsatzstelle'],
    Aufgabe2: ['faellig_art', 'mitupload'],
    Einsatzstelle2: ['einsatzland'],
    Notfallkontakt2: ['freiwilliger'],
    UserAufgaben: ['freiwilliger', 'aufgabe', 'erledigt'],
    CustomUser: ['person_cluster'],
    # Aufgabenprofil: ['aufgaben__aufgabe'],
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
        model = Team
        fields = '__all__'
        exclude = ['org', 'user']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['land'].queryset = Einsatzland2.objects.filter(org=self.request.user.org)

        add_customuser_fields(self, 'T')

        order_fields = ['first_name', 'last_name', 'email', 'person_cluster']
        self.order_fields(order_fields)

        add_person_cluster_field(self)          
        
    def save(self, commit=True):
        if not self.instance.pk:
            save_and_create_customuser(self)
            self.instance.save()
        else:
            self.instance.user.customuser.person_cluster = self.cleaned_data['person_cluster']
            self.instance.user.customuser.save()

        instance = super().save(commit=commit)

        save_person_cluster_field(self)
        
        return instance
    

class AddPersonClusterForm(OrgFormMixin, forms.ModelForm):
    class Meta:
        model = PersonCluster
        fields = '__all__'
        exclude = ['org']
        

model_to_form_mapping = {
    Einsatzland2: AddEinsatzlandForm,
    Einsatzstelle2: AddEinsatzstelleForm,
    Freiwilliger: AddFreiwilligerForm,
    Aufgabe2: AddAufgabeForm,
    Notfallkontakt2: AddNotfallkontaktForm,
    UserAufgaben: AddFreiwilligerAufgabenForm,
    Team: AddReferentenForm,
    CustomUser: AddUserForm,
    Attribute: AddAttributeForm,
    PersonCluster: AddPersonClusterForm
}
