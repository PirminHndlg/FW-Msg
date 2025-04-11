from django import forms
from .models import Feedback, Post2, Notfallkontakt2
from django.utils.translation import gettext_lazy as _

class FeedbackForm(forms.ModelForm):
    class Meta:
        model = Feedback
        fields = ['text', 'anonymous']

class AddNotifallkontaktForm(forms.ModelForm):
    class Meta:
        model = Notfallkontakt2
        fields = ['first_name', 'last_name', 'phone_work', 'phone', 'email']

class AddPostForm(forms.ModelForm):
    class Meta:
        model = Post2
        fields = ['title', 'text']
        widgets = {
            'text': forms.Textarea(attrs={'rows': 10}),
        }
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['title'].widget.attrs.update({'placeholder': _('Titel des Beitrags')})
        self.fields['text'].widget.attrs.update({'placeholder': _('Inhalt des Beitrags')})