from django import forms
from PIL import Image
from django.core.exceptions import ValidationError
from django.contrib.auth.models import User
from .models import ChatDirect, ChatGroup
from django.utils.translation import gettext_lazy as _


class ChatDirectForm(forms.ModelForm):
    class Meta:
        model = ChatDirect
        fields = ['users']

    def __init__(self, *args, org=None, current_user=None, **kwargs):
        super().__init__(*args, **kwargs)
        qs = User.objects.filter(customuser__org=org).order_by('customuser__person_cluster', 'first_name', 'last_name')
        if current_user and current_user.id:
            qs = qs.exclude(pk=current_user.id)
        qs = qs.exclude(customuser__person_cluster__view='B')
        qs = qs.select_related('customuser')
        self.fields['users'].queryset = qs
        self.fields['users'].label = _('Benutzer:in')
        self.fields['users'].widget.attrs.update({'class': 'form-select'})


class ChatGroupForm(forms.ModelForm):
    class Meta:
        model = ChatGroup
        fields = ['name', 'users']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, org=None, current_user=None, **kwargs):
        super().__init__(*args, **kwargs)
        qs = User.objects.filter(customuser__org=org).order_by('customuser__person_cluster', 'first_name', 'last_name')
        if current_user and current_user.id:
            qs = qs.exclude(pk=current_user.id)
        qs = qs.exclude(customuser__person_cluster__view='B')
        qs = qs.select_related('customuser')
        self.fields['users'].queryset = qs
        self.fields['users'].label = _('Mitglieder')
        self.fields['users'].widget.attrs.update({'class': 'form-select'})
        self.fields['name'].label = _('Gruppenname')


_PIL_FORMAT_EXTS = {"JPEG": ".jpg", "PNG": ".png", "GIF": ".gif", "WEBP": ".webp"}
CHAT_ATTACHMENT_ACCEPT = "image/jpeg,image/png,image/gif,image/webp,application/pdf,.pdf"


def validate_chat_attachment(upload):
    """Accept images (JPG/PNG/GIF/WEBP) and PDFs, detected by content.

    Sets ``upload.name`` to an extension matching the detected type so the
    stored file is served with the right content type. Raises ValidationError
    for anything else.
    """
    error = ValidationError(_('Nur Bilder (JPG, PNG, GIF, WEBP) oder PDF-Dateien erlaubt.'))
    upload.seek(0)
    header = upload.read(5)
    upload.seek(0)
    if header == b"%PDF-":
        upload.name = "attachment.pdf"
        return upload
    try:
        with Image.open(upload) as img:
            fmt = img.format
            img.verify()
    except Exception:
        raise error
    finally:
        upload.seek(0)
    ext = _PIL_FORMAT_EXTS.get(fmt)
    if not ext:
        raise error
    upload.name = f"attachment{ext}"
    return upload


def _chat_attachment_field():
    return forms.FileField(
        widget=forms.FileInput(attrs={'class': 'form-control', 'accept': CHAT_ATTACHMENT_ACCEPT}),
        label='',
        required=False,
        validators=[validate_chat_attachment],
    )


_CHAT_MESSAGE_WIDGET_ATTRS = {
    'class': 'form-control chat-message-input',
    'placeholder': _('Nachricht schreiben…'),
    'autocomplete': 'off',
    'rows': 1,
}


class SendDirectMessageForm(forms.Form):
    image = _chat_attachment_field()
    message = forms.CharField(
        widget=forms.Textarea(attrs=_CHAT_MESSAGE_WIDGET_ATTRS),
        label='',
        required=False,
    )

    def clean(self):
        cleaned = super().clean()
        message = (cleaned.get('message') or '').strip()
        image = cleaned.get('image')
        if not message and not image:
            raise ValidationError(_('Nachricht oder Anhang erforderlich.'))
        cleaned['message'] = message
        return cleaned


class SendGroupMessageForm(forms.Form):
    image = _chat_attachment_field()
    message = forms.CharField(
        widget=forms.Textarea(attrs=_CHAT_MESSAGE_WIDGET_ATTRS),
        label='',
        required=False,
    )

    def clean(self):
        cleaned = super().clean()
        message = (cleaned.get('message') or '').strip()
        image = cleaned.get('image')
        if not message and not image:
            raise ValidationError(_('Nachricht oder Anhang erforderlich.'))
        cleaned['message'] = message
        return cleaned
