from django import forms
from django.contrib import messages
from django.core.exceptions import FieldDoesNotExist

from FWMsg.middleware import get_current_request
from .models import Ampel2, BewerberKommentar, Feedback, PersonCluster, Post2, Notfallkontakt2, PostResponse, PostSurveyQuestion, PostSurveyAnswer, EinsatzstelleNotiz, MapLocation
from django.utils.translation import gettext_lazy as _
from Global.send_email import send_new_post_email
from django.forms.widgets import HiddenInput
import uuid
from typing import Any


class ActivePersonClusterFormMixin:
    """Hide inactive cluster choices while retaining existing relationships."""

    fields: Any
    instance: Any
    initial: Any
    _meta: Any

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._inactive_person_cluster_m2m = {}
        self._inactive_person_cluster_fk = {}

        for field_name, field in self.fields.items():
            if not isinstance(field, forms.ModelChoiceField):
                continue
            if field.queryset.model is not PersonCluster:
                continue

            field.queryset = field.queryset.filter(active=True)
            if not getattr(self.instance, 'pk', None):
                continue

            try:
                model_field = self._meta.model._meta.get_field(field_name)
            except (AttributeError, FieldDoesNotExist):
                continue

            if model_field.many_to_many:
                inactive_ids = list(
                    getattr(self.instance, field_name)
                    .filter(active=False)
                    .values_list('pk', flat=True)
                )
                if inactive_ids:
                    self._inactive_person_cluster_m2m[field_name] = inactive_ids
            elif model_field.many_to_one:
                current_cluster = getattr(self.instance, field_name, None)
                if current_cluster and not current_cluster.active:
                    self._inactive_person_cluster_fk[field_name] = current_cluster
                    field.required = False
                    self.initial.pop(field_name, None)

    def clean(self):
        cleaned_data = super().clean()  # pyright: ignore[reportAttributeAccessIssue]
        for field_name, current_cluster in self._inactive_person_cluster_fk.items():
            if not cleaned_data.get(field_name):
                cleaned_data[field_name] = current_cluster
        return cleaned_data

    def _save_m2m(self):
        super()._save_m2m()  # pyright: ignore[reportAttributeAccessIssue]
        for field_name, inactive_ids in self._inactive_person_cluster_m2m.items():
            getattr(self.instance, field_name).add(*inactive_ids)


class FeedbackForm(forms.ModelForm):
    class Meta:
        model = Feedback
        fields = ['text', 'anonymous']

class AddNotifallkontaktForm(forms.ModelForm):
    class Meta:
        model = Notfallkontakt2
        fields = ['first_name', 'last_name', 'phone_work', 'phone', 'email']
        
class AddAmpelmeldungForm(forms.ModelForm):
    submission_key = forms.UUIDField(widget=HiddenInput, required=False)

    class Meta:
        model = Ampel2
        fields = ['status', 'comment']
        
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        self.org = kwargs.pop('org', None)
        super().__init__(*args, **kwargs)
        self.fields['status'].widget.attrs.update({'class': 'form-select'})
        self.fields['comment'].widget.attrs.update({
            'class': 'form-control', 
            'rows': 4, 
            'required': 'true', 
            'placeholder': _('Wie geht es dir? Was hast du in der letzten Zeit gemacht? Schreibe einen kurzen Kommentar...'),
            'id': 'id_comment'
        })
        
        self.fields['status'].required = True
        self.fields['comment'].required = True
        self.fields['submission_key'].required = False


    def clean_status(self):
        value = (self.cleaned_data.get('status') or '').upper()
        if value not in ['R', 'G', 'Y']:
            raise forms.ValidationError(_('Ungültiger Status'))
        return value

    def save(self, commit=True):
        if not self.is_valid():
            raise ValueError('Form is not valid')

        key = self.cleaned_data.get('submission_key') or uuid.uuid4()

        # Idempotency by submission_key scoped to org
        existing = Ampel2.objects.filter(submission_key=key, org=self.org).first()
        if existing:
            return existing, False

        obj = Ampel2.objects.create(
            user=self.user,
            org=self.org,
            status=self.cleaned_data['status'],
            comment=self.cleaned_data.get('comment', ''),
            submission_key=key
        )
        return obj, True

class AddPostForm(ActivePersonClusterFormMixin, forms.ModelForm):
    has_survey = forms.BooleanField(required=False, label=_('Umfrage hinzufügen'), 
                                  help_text=_('Aktivieren, um eine einfache Umfrage zum Beitrag hinzuzufügen'))
    image = forms.ImageField(required=False, label=_('Bild'), help_text=_('Bild des Posts'))
    survey_question = forms.CharField(required=False, max_length=200, 
                                    label=_('Umfragefrage'), 
                                    help_text=_('Geben Sie die Frage für Ihre Umfrage ein'))
    
    # Dynamic answer fields
    answer_1 = forms.CharField(required=False, max_length=100, 
                             label=_('Antwort 1'), 
                             help_text=_('Erste Antwortmöglichkeit'))
    answer_2 = forms.CharField(required=False, max_length=100, 
                             label=_('Antwort 2'), 
                             help_text=_('Zweite Antwortmöglichkeit'))
    answer_3 = forms.CharField(required=False, max_length=100, 
                             label=_('Antwort 3'), 
                             help_text=_('Dritte Antwortmöglichkeit (optional)'))
    answer_4 = forms.CharField(required=False, max_length=100, 
                             label=_('Antwort 4'), 
                             help_text=_('Vierte Antwortmöglichkeit (optional)'))
    answer_5 = forms.CharField(required=False, max_length=100, 
                             label=_('Antwort 5'), 
                             help_text=_('Fünfte Antwortmöglichkeit (optional)'))
    
    class Meta:
        model = Post2
        fields = ['title', 'text', 'image', 'has_survey', 'person_cluster']
        widgets = {
            'text': forms.Textarea(attrs={'rows': 10}),
            'person_cluster': forms.CheckboxSelectMultiple(),
        }
    
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['title'].widget.attrs.update({'placeholder': _('Titel des Beitrags')})
        self.fields['text'].required = False
        self.fields['text'].widget.attrs.update({'placeholder': _('Inhalt des Beitrags')})
        self.fields['image'].required = False
        self.fields['image'].widget.attrs.update({'class': 'form-control', 'accept': 'image/*', 'id': 'id_image'})
        self.fields['person_cluster'].widget.attrs.update({'class': 'form-check-input'})

        # Get all person clusters
        request = get_current_request()
        if request and hasattr(request, 'user') and hasattr(request.user, 'customuser'):
            
            # Filter queryset based on user role
            if request.user.role == 'O':
                self.fields['person_cluster'].queryset = PersonCluster.selectable_for_org(
                    request.user.org
                ).order_by('name')
                self.fields['person_cluster'].required = False
            else:
                # For non-admin users, just show their own person_cluster
                person_cluster_id = request.user.person_cluster.id
                self.fields['person_cluster'].queryset = PersonCluster.selectable_for_org(
                    request.user.org,
                    id=person_cluster_id,
                )
                # Pre-select their cluster
                if not self.instance.pk:  # Only for new instances
                    self.initial['person_cluster'] = [person_cluster_id]
            
                self.fields['person_cluster'].widget.attrs.update({'disabled': 'true'})
            
        if self.instance.pk:
            self.fields['image'].initial = self.instance.image
            
    def clean(self):
        cleaned_data = super().clean()
        has_survey = cleaned_data.get('has_survey')
        image = cleaned_data.get('image')
        
        if image and image.size > 10 * 1024 * 1024: # 10MB
            self.add_error('image', _('Das Bild darf nicht größer als 10MB sein'))
            
        if has_survey:
            # Survey question is required if has_survey is checked
            survey_question = cleaned_data.get('survey_question')
            if not survey_question:
                self.add_error('survey_question', _('Bitte geben Sie eine Frage für die Umfrage ein'))
                
            # At least two answers are required
            answer_1 = cleaned_data.get('answer_1')
            answer_2 = cleaned_data.get('answer_2')
            
            if not answer_1:
                self.add_error('answer_1', _('Mindestens zwei Antwortmöglichkeiten sind erforderlich'))
            if not answer_2:
                self.add_error('answer_2', _('Mindestens zwei Antwortmöglichkeiten sind erforderlich'))
                
        return cleaned_data
    
    def save(self, commit=True):
        post = super().save(commit=False)

        post.has_survey = self.cleaned_data.get('has_survey', False)
        
        # Only update image if a new one was uploaded
        image = self.cleaned_data.get('image')
        if image:
            post.image = image
            
        if commit:
            post.save()
            self.save_m2m()
            self.save_answers()
    
        return post
    
    def save_answers(self):
        # Create survey question and answers if has_survey is checked
        if self.instance.has_survey:
            question_text = self.cleaned_data.get('survey_question')
            if question_text:
                # Create or update the survey question
                question, created = PostSurveyQuestion.objects.update_or_create(
                    post=self.instance,
                    org=self.instance.org,
                    defaults={'question_text': question_text}
                )

                if not created:
                    # Get existing answers to compare with new ones
                    existing_answers = {answer.answer_text: answer for answer in 
                                      PostSurveyAnswer.objects.filter(question=question)}
                    
                    # Collect new answers
                    new_answers = []
                    for i in range(1, 6):
                        answer_text = self.cleaned_data.get(f'answer_{i}')
                        if answer_text:
                            new_answers.append(answer_text)
                    
                    # Check if answers have changed
                    answers_changed = len(existing_answers) != len(new_answers)
                    if not answers_changed:
                        for answer_text in new_answers:
                            if answer_text not in existing_answers:
                                answers_changed = True
                                break
                    
                    # Only delete old answers if there were changes
                    if answers_changed:
                        PostSurveyAnswer.objects.filter(question=question).delete()
                        # Create new answers
                        for answer_text in new_answers:
                            PostSurveyAnswer.objects.create(
                                question=question,
                                org=self.instance.org,
                                answer_text=answer_text
                            )
                    else:
                        # No changes to answers, do nothing
                        pass
                else:
                    # This is a new question, create all answers
                    for i in range(1, 6):
                        answer_text = self.cleaned_data.get(f'answer_{i}')
                        if answer_text:
                            PostSurveyAnswer.objects.create(
                                question=question,
                                org=self.instance.org,
                                answer_text=answer_text
                            )
                            

class PostResponseForm(forms.ModelForm):
    image = forms.ImageField(required=False, label=_('Bild'), help_text=_('Bild der Antwort'))
    with_notification = forms.BooleanField(required=False, label=_('Andere Benutzer:innen benachrichtigen'), help_text=_('Sende eine Benachrichtigung an andere Benutzer:innen, die an diesem Post interessiert sind'))
    
    class Meta:
        model = PostResponse
        fields = ['text', 'image']
        widgets = {
            'text': forms.Textarea(attrs={'rows': 10}),
        }
        
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        self.original_post = kwargs.pop('original_post', None)
        super().__init__(*args, **kwargs)
        self.fields['text'].widget.attrs.update({'placeholder': _('Text der Antwort')})
        self.fields['with_notification'].widget.attrs.update({'class': 'form-check-input'})
        self.fields['with_notification'].required = False
        self.fields['with_notification'].initial = True
        self.fields['image'].widget.attrs.update({'class': 'form-control', 'accept': 'image/*', 'id': 'id_response_image'})
    
    def clean(self):
        cleaned_data = super().clean()
        text = cleaned_data.get('text')
        image = cleaned_data.get('image')
        if not text and not image:
            self.add_error('text', _('Mindestens ein Text oder Bild ist erforderlich'))
            self.add_error('image', _('Mindestens ein Text oder Bild ist erforderlich'))
            return None
        return cleaned_data
        
    def save(self, commit=True):
        response = super().save(commit=False)
        response.user = self.user
        response.org = self.user.org
        response.original_post = self.original_post
        if commit:
            response.save()
            
        # with_notification
        if self.cleaned_data.get('with_notification'):
            from Global.tasks import send_post_response_email_task
            send_post_response_email_task.s(response.id).apply_async(countdown=15*60)
            
        return response

                
class EinsatzstelleNotizForm(forms.ModelForm):
    class Meta:
        model = EinsatzstelleNotiz
        fields = ['notiz']
        exclude = ['einsatzstelle']

    def __init__(self, *args, **kwargs):
        self.org = kwargs.pop('org', None)
        self.einsatzstelle = kwargs.pop('einsatzstelle', None)
        self.request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
        self.fields['notiz'].widget.attrs.update({'placeholder': _('Notiz')})
        self.fields['notiz'].required = True
        
    def save(self, commit=True):
        notiz = super().save(commit=False)
        notiz.user = self.request.user
        notiz.org = self.org
        notiz.einsatzstelle = self.einsatzstelle
        if commit:
            notiz.save()
        return notiz


class BewerberKommentarForm(forms.ModelForm):
    class Meta:
        model = BewerberKommentar
        fields = ['comment']
        labels = {
            'comment': _('Kommentar'),
        }
        widgets = {
            'comment': forms.Textarea(attrs={
                'rows': 6,
                'placeholder': _('Geben Sie hier Ihren Kommentar ein...')
            }),
        }
        
class KarteForm(forms.ModelForm):
    class Meta:
        model = MapLocation
        fields = ['zip_code', 'city', 'country', 'visibility']
        
    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        if self.request and hasattr(self.request, 'user') and hasattr(self.request.user, 'org'):
            self.org = self.request.user.org
        else:
            self.org = None
            
        super().__init__(*args, **kwargs)
        self.fields['zip_code'].widget.attrs.update({'placeholder': 'optional'})
        self.fields['city'].widget.attrs.update({'placeholder': _('Stadt')})
        self.fields['country'].widget.attrs.update({'placeholder': _('Land')})
        self.fields['zip_code'].required = False
        self.fields['visibility'].widget.attrs.update({'class': 'form-select'})
        self.fields['visibility'].required = True
        self.fields['visibility'].initial = 'F'