import uuid
from pathlib import Path

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from Global.models import OrgModel
from simple_history.models import HistoricalRecords
from Global.models import get_random_hash

_CHAT_IMAGE_EXTS = frozenset({".jpg", ".jpeg", ".png", ".gif", ".webp"})


def chat_message_image_upload_to(instance, filename):
    """Store files as ``chat_images/<uuid>.<ext>``; sets ``image_identifier`` when missing."""
    ext = Path(filename).suffix.lower()
    if ext not in _CHAT_IMAGE_EXTS:
        ext = ""
    if instance.image_identifier is None:
        instance.image_identifier = uuid.uuid4()
    return f"chat_images/{instance.image_identifier}{ext}"


def _sync_chat_message_image_identifier(instance):
    if not instance.image:
        instance.image_identifier = None
    elif instance.image_identifier is None:
        instance.image_identifier = uuid.uuid4()


class ChatMessageImageUrlMixin:
    """Opaque image URLs (UUID); never expose storage paths to clients."""

    def get_image_public_url(self):
        from django.urls import reverse

        if (
            not getattr(self, "image", None)
            or not self.image.name
            or not getattr(self, "image_identifier", None)
        ):
            return None
        return reverse(
            "serve_chat_image",
            kwargs={"image_identifier": self.image_identifier},
        )


class ChatDirect(OrgModel):
    identifier = models.CharField(max_length=255, unique=True, null=True, blank=True)
    users = models.ManyToManyField(User, related_name='chat_directs')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    history = HistoricalRecords()

    def get_identifier(self):
        identifier = self.identifier
        if not identifier:
            identifier = get_random_hash(str(self.users.all().values_list('id', flat=True)), 64)
            # hash collision check
            while ChatDirect.objects.filter(identifier=identifier, org=self.org).exists():
                identifier = get_random_hash(str(self.users.all().values_list('id', flat=True)), 64)
            self.identifier = identifier
            self.save()
        return identifier
    
    def get_last_message(self):
        first = ChatMessageDirect.objects.filter(chat=self).order_by('-created_at').first()
        if first:
            return first.created_at 
        return timezone.now()

    def __str__(self):
        return f"{', '.join([u.username for u in self.users.all()])}"
    
    
class ChatGroup(OrgModel):
    identifier = models.CharField(max_length=255, unique=True, null=True, blank=True)
    users = models.ManyToManyField(User, related_name='chat_groups')
    name = models.CharField(max_length=255)
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL,
        related_name='created_chat_groups',
        null=True, blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    history = HistoricalRecords()
    
    def get_identifier(self):
        identifier = self.identifier
        if not identifier:
            identifier = get_random_hash(str(self.users.all().values_list('id', flat=True)), 64)
            # hash collision check
            while ChatGroup.objects.filter(identifier=identifier, org=self.org).exists():
                identifier = get_random_hash(str(self.users.all().values_list('id', flat=True)), 64)
            self.identifier = identifier
            self.save()
        return identifier
    
    def get_last_message(self):
        first = ChatMessageGroup.objects.filter(chat=self).order_by('-created_at').first()
        if first:
            return first.created_at 
        return timezone.now()

    def __str__(self):
        return self.name


class ChatMessageDirect(ChatMessageImageUrlMixin, OrgModel):
    chat = models.ForeignKey(ChatDirect, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    message = models.TextField()
    image = models.ImageField(
        upload_to=chat_message_image_upload_to, blank=True, null=True
    )
    image_identifier = models.UUIDField(
        null=True, blank=True, editable=False, db_index=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    read = models.BooleanField(default=False)

    history = HistoricalRecords()

    def save(self, *args, **kwargs):
        _sync_chat_message_image_identifier(self)
        super().save(*args, **kwargs)

    def mark_as_read(self):
        self.read = True
        self.save()

    def __str__(self):
        return self.message
    
    
class ChatMessageGroup(ChatMessageImageUrlMixin, OrgModel):
    chat = models.ForeignKey(ChatGroup, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    message = models.TextField()
    image = models.ImageField(
        upload_to=chat_message_image_upload_to, blank=True, null=True
    )
    image_identifier = models.UUIDField(
        null=True, blank=True, editable=False, db_index=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    read_by = models.ManyToManyField(User, related_name='chat_message_group_read_by')
    
    history = HistoricalRecords()

    def save(self, *args, **kwargs):
        _sync_chat_message_image_identifier(self)
        super().save(*args, **kwargs)

    def mark_as_read_by(self, user):
        self.read_by.add(user)
        self.save()
        
    def __str__(self):
        return self.message