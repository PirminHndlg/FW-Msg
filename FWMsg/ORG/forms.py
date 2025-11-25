from datetime import datetime
import random
import string
from django import forms
from django.contrib import messages
from django.db import models
from django.contrib.auth.models import User
from django.forms import inlineformset_factory
from django.utils import timezone
from django.conf import settings
from django.db.models import Q
from django.utils.translation import gettext as _

from Ehemalige.models import Ehemalige
from Global.models import (
    Attribute, Aufgabe2, AufgabenCluster, KalenderEvent,
    UserAufgaben, Post2, Bilder2, CustomUser,
    BilderGallery2, Ampel2, ProfilUser2, Notfallkontakt2, UserAttribute, 
    PersonCluster, Einsatzland2, Einsatzstelle2,
    AufgabeZwischenschritte2
)
from FW.models import Freiwilliger
from TEAM.models import Team
from BW.models import ApplicationText, ApplicationQuestion, ApplicationFileQuestion, Bewerber


# Custom widget for multiple file uploads
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
            result = single_file_clean(data, initial)
        return result


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

    person_clusters = PersonCluster.objects.filter(org=self.request.user.org, view=view)
    self.fields['person_cluster'] = forms.ModelChoiceField(
        queryset=person_clusters,
        widget=forms.Select(attrs={'class': 'form-control'}),
        required=True,
        label='Benutzergruppe'
    )
    if self.instance and self.instance.pk:
        self.fields['person_cluster'].initial = self.instance.user.person_cluster
        
    if person_clusters.count() == 1:
        self.fields['person_cluster'].initial = person_clusters.first()


def add_person_cluster_field(self):
    person_cluster_typ = self.instance.user.person_cluster if self.instance and self.instance.pk else None
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
    for attribute in Attribute.objects.filter(org=self.request.user.org, person_cluster=self.instance.user.person_cluster):
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
        
        # Dependent select: einsatzstelle2 filtered by einsatzland2
        self.fields['einsatzstelle2'].queryset = Einsatzstelle2.objects.none()
        selected_land = None
        try:
            raw_value = self.data.get('einsatzland2') if hasattr(self, 'data') else None
            value_str = str(raw_value) if raw_value is not None else ''
            if value_str.isdigit():
                selected_land = int(value_str)
            elif self.instance and getattr(self.instance, 'einsatzland2_id', None):
                selected_land = self.instance.einsatzland2_id
        except Exception:
            selected_land = None
        if selected_land:
            self.fields['einsatzstelle2'].queryset = Einsatzstelle2.objects.filter(org=self.request.user.org, land_id=selected_land)
                    
                
    def clean(self):
        cleaned_data = super().clean()
        einsatzstelle = cleaned_data.get('einsatzstelle2')
        einsatzland = cleaned_data.get('einsatzland2')
        if einsatzstelle and einsatzland and einsatzstelle.land_id != einsatzland.id:
            self.add_error('einsatzstelle2', 'Einsatzstelle gehört nicht zum ausgewählten Einsatzland')
        return cleaned_data

    def save(self, commit=True):
        if not self.instance.pk:
            save_and_create_customuser(self)
            self.instance.save()
        else:
            self.instance.user.customuser.person_cluster = self.cleaned_data['person_cluster']
            self.instance.user.customuser.save()

        instance = super().save(commit=commit)
        
        if self.cleaned_data['first_name'] != self.instance.user.first_name:
            self.instance.user.first_name = self.cleaned_data['first_name']
            self.instance.user.save()
        
        if self.cleaned_data['last_name'] != self.instance.user.last_name:
            self.instance.user.last_name = self.cleaned_data['last_name']
            self.instance.user.save()
        
        if self.cleaned_data['email'] != self.instance.user.email:
            self.instance.user.email = self.cleaned_data['email']
            self.instance.user.save()
        
        save_person_cluster_field(self)
        
        return instance
    

# Form to create a new Bewerber and upload the application PDF
class AddBewerberApplicationPdfForm(OrgFormMixin, forms.ModelForm):
    # Custom field for multiple PDF uploads
    pdf_files = MultipleFileField(
        widget=MultipleFileInput(attrs={'accept': 'application/pdf'}),
        required=False,
        label='PDF-Dateien der Bewerbung',
        help_text='Mehrere PDF-Dateien können ausgewählt werden. Diese werden zu einer einzigen PDF zusammengeführt.'
    )
    
    class Meta:
        model = Bewerber
        fields = ['interview_persons', 'zuteilung', 'zuteilung_freigegeben', 'reaktion_auf_zuteilung', 'endbewertung']
        exclude = ['org', 'application_pdf']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        add_customuser_fields(self, 'B')
        
        # Filter interview_persons to only show users from team, ehemalige, or org
        self.fields['interview_persons'].queryset = User.objects.filter(
            customuser__org=self.request.user.org,
            customuser__person_cluster__view__in=['T', 'E', 'O']
        ).order_by('last_name', 'first_name')
        self.fields['interview_persons'].label = 'Interviewpersonen'
        self.fields['interview_persons'].help_text = 'Wählen Sie die Personen aus, die das Interview durchgeführt haben.'
        
        order_fields = ['first_name', 'last_name', 'email', 'person_cluster',  'pdf_files', 'interview_persons', 'endbewertung', 'zuteilung', 'zuteilung_freigegeben', 'reaktion_auf_zuteilung']
        self.order_fields(order_fields)
        
        # Separate, non-model field for profile picture upload
        self.fields['profil_picture'] = forms.ImageField(required=False)
        self.fields['profil_picture'].widget = forms.FileInput(attrs={'accept': 'image/*'})
        self.fields['profil_picture'].validators.append(self.validate_image_only)
        self.fields['profil_picture'].label = 'Profilbild'
        self.fields['profil_picture'].initial = self.instance.user.customuser.profil_picture if self.instance and self.instance.pk else None
        
        # Show existing profile picture if it exists
        if self.instance.pk and self.instance.user.customuser.profil_picture:
            from django.urls import reverse
            from django.utils.safestring import mark_safe
            picture_url = reverse('serve_profil_picture', kwargs={'user_identifier': self.instance.user.customuser.get_identifier()})
            self.fields['profil_picture'].help_text = mark_safe(
                f'<div style="margin-top: 10px;">'
                f'<p>Aktuelles Profilbild:</p>'
                f'<img src="{picture_url}" alt="Profilbild" style="max-width: 200px; max-height: 200px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">'
                f'</div>'
            )
        
        # Show existing application PDF if it exists
        if self.instance.pk and self.instance.application_pdf:
            from django.urls import reverse
            from django.utils.safestring import mark_safe
            pdf_url = reverse('application_answer_download', args=[self.instance.id])
            self.fields['pdf_files'].help_text = mark_safe(
                f'<div style="margin-top: 10px; padding: 12px; background-color: #f8f9fa; border-radius: 8px; border-left: 4px solid #007bff;">'
                f'<p style="margin-bottom: 8px;"><strong>Aktuelles Bewerbungs-PDF:</strong></p>'
                f'<a href="{pdf_url}" target="_blank" class="btn btn-sm btn-outline-primary" style="text-decoration: none;">'
                f'<i class="bi bi-file-earmark-pdf me-1"></i>PDF herunterladen'
                f'</a>'
                f'<p style="margin-top: 8px; margin-bottom: 0; font-size: 0.875rem; color: #6c757d;">'
                f'Wenn neue PDFs hochgeladen werden, wird das aktuelle PDF ersetzt.'
                f'</p>'
                f'</div>'
                f'<div style="margin-top: 5px;">{self.fields["pdf_files"].help_text or ""}</div>'
            )
        
        add_person_cluster_field(self)
        
        
    def validate_image_only(self, value):
        """Ensure only image files are uploaded"""
        if value and hasattr(value, 'content_type'):
            if value.content_type not in ['image/jpeg', 'image/png', 'image/gif', 'image/webp']:
                raise forms.ValidationError("Nur Bilddateien werden akzeptiert.")
        elif value and hasattr(value, 'name'):
            if not value.name.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp')):
                raise forms.ValidationError("Nur Bilddateien werden akzeptiert.")
        return value

    def validate_pdf_files(self, files):
        """Validate that all uploaded files are PDFs"""
        for file in files:
            if hasattr(file, 'content_type'):
                if file.content_type != 'application/pdf':
                    raise forms.ValidationError(f"Die Datei '{file.name}' ist kein PDF. Nur PDF-Dateien werden akzeptiert.")
            elif hasattr(file, 'name'):
                if not file.name.lower().endswith('.pdf'):
                    raise forms.ValidationError(f"Die Datei '{file.name}' ist kein PDF. Nur PDF-Dateien werden akzeptiert.")
        return files
    
    def merge_pdfs(self, pdf_files):
        """Merge multiple PDF files into a single PDF"""
        from PyPDF2 import PdfMerger
        from django.core.files.base import ContentFile
        import io
        
        if not pdf_files:
            return None
        
        # Filter out None values
        pdf_files = [f for f in pdf_files if f]
        
        if not pdf_files:
            return None
        
        # If only one file, read it into memory and return
        if len(pdf_files) == 1:
            pdf_file = pdf_files[0]
            pdf_file.seek(0)
            file_content = pdf_file.read()
            return ContentFile(file_content, name=pdf_file.name)
        
        # Merge multiple PDFs
        merger = PdfMerger()
        file_buffers = []
        
        try:
            # Read all files into memory immediately to avoid temp file cleanup issues
            for pdf_file in pdf_files:
                try:
                    # Read the entire file into a BytesIO buffer
                    pdf_file.seek(0)
                    file_data = pdf_file.read()
                    buffer = io.BytesIO(file_data)
                    file_buffers.append(buffer)
                except Exception as read_error:
                    # Log individual file read errors
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.error(f"Error reading PDF file {getattr(pdf_file, 'name', 'unknown')}: {str(read_error)}")
                    raise forms.ValidationError(f"Fehler beim Lesen der Datei '{getattr(pdf_file, 'name', 'unknown')}'. Bitte versuchen Sie es erneut.")
            
            # Now merge from the in-memory buffers
            for buffer in file_buffers:
                buffer.seek(0)
                merger.append(buffer)
            
            # Write merged PDF to a BytesIO object
            output = io.BytesIO()
            merger.write(output)
            
            # Reset pointer to beginning
            output.seek(0)
            
            # Create a ContentFile from the merged PDF
            merged_filename = f"bewerbung_{pdf_files[0].name}"
            result = ContentFile(output.read(), name=merged_filename)
            
            return result
            
        except forms.ValidationError:
            # Re-raise validation errors as-is
            raise
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error merging PDFs: {str(e)}", exc_info=True)
            raise forms.ValidationError(f"Fehler beim Zusammenführen der PDFs: {str(e)}")
        finally:
            # Always cleanup resources
            try:
                merger.close()
            except:
                pass
            
            # Close all buffers
            for buffer in file_buffers:
                try:
                    buffer.close()
                except:
                    pass
    
    def clean_pdf_files(self):
        """Validate PDF files from request"""
        # The MultipleFileField already handles getting the files
        files = self.cleaned_data.get('pdf_files', [])
        
        # Handle None case
        if files is None:
            return []
        
        # Ensure files is always a list
        if not isinstance(files, list):
            files = [files] if files else []
        
        # Filter out None/empty values
        files = [f for f in files if f]
        
        if files:
            self.validate_pdf_files(files)
        
        return files

    def save(self, commit=True):
        if not self.instance.pk:
            save_and_create_customuser(self)
            self.instance.save()
        else:
            self.instance.user.customuser.person_cluster = self.cleaned_data['person_cluster']
            self.instance.user.customuser.save()
            
        if self.cleaned_data.get('profil_picture'):
            self.instance.user.customuser.profil_picture = self.cleaned_data['profil_picture']
            self.instance.user.customuser.create_small_image()
            self.instance.user.customuser.save()

        # Handle PDF files - merge if multiple files uploaded
        pdf_files = self.cleaned_data.get('pdf_files')
        if pdf_files:
            try:
                merged_pdf = self.merge_pdfs(pdf_files)
                if merged_pdf:
                    self.instance.application_pdf = merged_pdf
            except Exception as e:
                # Log the error for debugging in production
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Error merging PDFs for Bewerber: {str(e)}", exc_info=True)
                # Re-raise as a validation error so user gets feedback
                raise forms.ValidationError(f"Fehler beim Verarbeiten der PDF-Dateien. Bitte versuchen Sie es erneut.")

        instance = super().save(commit=commit)
        
        if self.cleaned_data['first_name'] != self.instance.user.first_name:
            self.instance.user.first_name = self.cleaned_data['first_name']
            self.instance.user.save()
        
        if self.cleaned_data['last_name'] != self.instance.user.last_name:
            self.instance.user.last_name = self.cleaned_data['last_name']
            self.instance.user.save()
        
        if self.cleaned_data['email'] != self.instance.user.email:
            self.instance.user.email = self.cleaned_data['email']
            self.instance.user.save()
            
        self.instance.user.customuser.update_identifier()
            
        instance.abgeschlossen = True
        instance.abgeschlossen_am = timezone.now()
        instance.save()
        
        save_person_cluster_field(self)
        
        return instance
        

class AddAufgabenClusterForm(OrgFormMixin, forms.ModelForm):
    class Meta:
        model = AufgabenCluster
        fields = '__all__'
        exclude = ['org']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['person_cluster'].queryset = PersonCluster.objects.filter(org=self.request.user.org)


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
        # Count only forms with content, not empty extra forms
        try:
            self.zwischenschritte_count = sum(1 for form in self.zwischenschritte.forms if form.instance.pk or (form.is_bound and any(form.cleaned_data.values())))
        except:
            self.zwischenschritte_count = 0

        self.fields['wiederholung_ende'] = forms.DateField(
            widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            help_text='Datum, bis zu dem die Aufgabe wiederholt wird',
            required=False
        )

        self.fields['person_cluster'].queryset = PersonCluster.objects.filter(org=self.request.user.org)

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
    Aufgabe2,
    AufgabeZwischenschritte2,
    fields=['name', 'beschreibung'],
    extra=4,
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
        self.fields['benachrichtigung_cc'].help_text = 'Hier weitere E-Mail-Adressen eingeben, die eine Mail erhalten sollen, wenn die Aufgabe erledigt wurde'

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
    geburtsdatum = forms.DateField(required=False, label='Geburtsdatum', widget=forms.DateInput(attrs={'type': 'date'}))
    email = forms.EmailField(required=False, label='Email')

    class Meta:
        model = CustomUser
        fields = ['username', 'first_name', 'last_name', 'person_cluster', 'geburtsdatum', 'email', 'einmalpasswort', 'profil_picture']
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
        

class AddKalenderEventForm(OrgFormMixin, forms.ModelForm):
    person_cluster = forms.ModelMultipleChoiceField(
        queryset=PersonCluster.objects.none(),
        required=False,
        label='Benutzergruppen',
        help_text='Wählen Sie Benutzergruppen aus, deren Mitglieder automatisch zum Termin hinzugefügt werden sollen'
    )
    
    # Add separate date and time fields
    start_date = forms.DateField(
        required=True,
        label='Startdatum',
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )
    start_time = forms.TimeField(
        required=False,
        label='Startzeit',
        widget=forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'})
    )
    end_date = forms.DateField(
        required=True,
        label='Enddatum',
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )
    end_time = forms.TimeField(
        required=False,
        label='Endzeit',
        widget=forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'})
    )

    class Meta:
        model = KalenderEvent
        fields = '__all__'
        exclude = ['org', 'mail_reminder_sent_to', 'start', 'end']
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['person_cluster'].queryset = PersonCluster.objects.filter(org=self.request.user.org)
        self.fields['user'].required = False
        
        # Set initial values for date and time fields if instance exists
        if self.instance and self.instance.pk:
            if self.instance.start:
                start_local = timezone.localtime(self.instance.start)
                self.fields['start_date'].initial = start_local.date()
                self.fields['start_time'].initial = start_local.time()
            if self.instance.end:
                end_local = timezone.localtime(self.instance.end)
                self.fields['end_date'].initial = end_local.date()
                self.fields['end_time'].initial = end_local.time()
        
        # Reorder fields to put person_cluster right after user
        field_order = ['title', 'user', 'person_cluster', 'start_date', 'start_time', 'end_date', 'end_time', 'location', 'description']
        self.order_fields(field_order)
        
    def _clean_time(self):
        cleaned_data = self.cleaned_data
        start_date = cleaned_data.get('start_date')
        start_time = cleaned_data.get('start_time')
        end_date = cleaned_data.get('end_date')
        end_time = cleaned_data.get('end_time')
        
        if not start_time:
            start_time = datetime.strptime('00:00', '%H:%M').time()
        if not end_time:
            end_time = datetime.strptime('23:59', '%H:%M').time()
            
        # Create datetime objects with the exact time input by the user
        start = datetime.combine(start_date, start_time)
        end = datetime.combine(end_date, end_time)
        
        if start > end:
            self.add_error('end_time', 'Die Endzeit muss nach der Startzeit liegen.')
            
        return start, end
        
    def clean(self):
        cleaned_data = super().clean()
        
        start, end = self._clean_time()
        
        cleaned_data['start'] = start
        cleaned_data['end'] = end
        
        return cleaned_data
        
    def save(self, commit=True):
        from ORG.tasks import send_mail_calendar_reminder_task
        
        start, end = self._clean_time()
        
        instance = super().save(commit=False)
        instance.org = self.request.user.org
        instance.start = start
        instance.end = end
        
        if commit:
            instance.save()
            # Save many-to-many relationships
            self.save_m2m()
            
            # Add users from selected person clusters
            if 'person_cluster' in self.cleaned_data:
                selected_clusters = self.cleaned_data['person_cluster']
                for cluster in selected_clusters:
                    # Get all users from the cluster
                    users = User.objects.filter(customuser__person_cluster=cluster, customuser__org=self.request.user.org)
                    # Add them to the event's users
                    instance.user.add(*users)
        
            mail_task_delay = 5*60
            for current_user in instance.user.all():
                if not instance.mail_reminder_sent_to.filter(id=current_user.id).exists():
                    send_mail_calendar_reminder_task.s(instance.id, current_user.id).apply_async(countdown=mail_task_delay)
            
            messages.success(self.request, _('Kalendereintrag erfolgreich gespeichert. Mail-Erinnerung wird in {mail_task_delay_formatted} Minuten gesendet.').format(mail_task_delay_formatted=int(mail_task_delay/60)))
        
        return instance
    
class AddApplicationTextForm(OrgFormMixin, forms.ModelForm):
    class Meta:
        model = ApplicationText
        fields = '__all__'
        exclude = ['org']
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['welcome'].widget = forms.Textarea(attrs={'rows': 4})
        self.fields['deadline'].widget = forms.DateInput(
            attrs={'type': 'date', 'class': 'form-control'},
            format='%Y-%m-%d'
        )
        self.fields['footer'].widget = forms.Textarea(attrs={'rows': 4})
        
class AddApplicationQuestionForm(OrgFormMixin, forms.ModelForm):
    class Meta:
        model = ApplicationQuestion
        fields = '__all__'
        exclude = ['org']
        
class AddApplicationFileQuestionForm(OrgFormMixin, forms.ModelForm):
    class Meta:
        model = ApplicationFileQuestion
        fields = '__all__'
        exclude = ['org']
        

class AccessibleByTeamMemberForm(OrgFormMixin, forms.ModelForm):
    class Meta:
        model = Bewerber
        fields = ['accessible_by_team_member']
        
    def __init__(self, *args, **kwargs):
        self.org = kwargs.pop('org', None)
        super().__init__(*args, **kwargs)
        
        # Get team members and alumni from the same organization
        person_cluster = PersonCluster.objects.filter(
            Q(view='T') | Q(view='E'),
            org=self.org
        )
        
        # Use checkboxes for multiple selection
        self.fields['accessible_by_team_member'].widget = forms.CheckboxSelectMultiple(
            attrs={'class': 'form-check-input'}
        )
        
        users = User.objects.filter(
            customuser__person_cluster__in=person_cluster,
            customuser__org=self.org
        ).order_by('customuser__person_cluster').distinct()
        
        self.fields['accessible_by_team_member'].queryset = users
        
        self.fields['accessible_by_team_member'].label = 'Teammitglieder auswählen'
        
    def save(self, commit=True):
        instance = super().save(commit=False)
        if commit:
            instance.save()
            # Save many-to-many relationships
            self.save_m2m()
        return instance
    
    
class AddEhemaligeForm(OrgFormMixin, forms.ModelForm):
    class Meta:
        model = Ehemalige
        fields = '__all__'
        exclude = ['org', 'user']
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['land'].queryset = Einsatzland2.objects.filter(org=self.request.user.org)
        add_customuser_fields(self, 'E')
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
    PersonCluster: AddPersonClusterForm,
    AufgabenCluster: AddAufgabenClusterForm,
    KalenderEvent: AddKalenderEventForm,
    Bewerber: AddBewerberApplicationPdfForm,
    ApplicationText: AddApplicationTextForm,
    ApplicationQuestion: AddApplicationQuestionForm,
    ApplicationFileQuestion: AddApplicationFileQuestionForm,
    Ehemalige: AddEhemaligeForm
}
