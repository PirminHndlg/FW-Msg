import json
import mimetypes
from pathlib import Path

from django.contrib import messages as django_messages
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, HttpResponseNotFound, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from django.contrib.auth.models import User
from Global.models import Ampel2
from Global.views import check_organization_context

from .ampel_access import (
    resolve_ampel,
    resolve_ampel_for_direct_reply,
    user_can_reply_to_ampel_in_direct_chat,
    user_can_view_ampel,
    user_is_ampel_staff,
)

from .badge_utils import (
    broadcast_chat_edit_to_room,
    broadcast_chat_message_to_room,
    broadcast_direct_message_read_if_needed,
    broadcast_unread_badge_for_user,
    get_unread_chat_message_count,
)
from .forms import ChatDirectForm, ChatGroupForm, SendDirectMessageForm, SendGroupMessageForm
from .models import ChatDirect, ChatGroup, ChatMessageDirect, ChatMessageGroup
from .tasks import notify_users_about_new_direct_chat_message, notify_users_about_new_group_chat_message, notify_users_about_new_group_chat
from django.utils.translation import gettext_lazy as _

def _ampel_payload(ampel):
    if ampel is None:
        return None
    return {
        "status": ampel.status,
        "comment": ampel.comment or "",
    }


def _chat_message_payload(msg, user, viewer=None):
    """JSON-serializable dict aligned with ChatConsumer.chat_message event shape."""
    image_url = msg.get_image_public_url()
    payload = {
        "id": msg.id,
        "user": str(user),
        "user_id": user.id,
        "message": msg.message,
        "created_at": msg.created_at.strftime("%d.%m.%Y %H:%M"),
        "image_url": image_url,
        "is_edited": msg.is_edited,
    }
    if viewer is not None and viewer.is_authenticated and msg.user_id == viewer.id:
        payload["can_edit"] = msg.can_be_edited()
        if isinstance(msg, ChatMessageDirect):
            payload["is_read"] = msg.read
    ampel = getattr(msg, "answer_to_ampel", None)
    if ampel is not None:
        payload["ampel_user_id"] = ampel.user_id
        if viewer is None or user_can_view_ampel(viewer, ampel):
            payload["ampel"] = _ampel_payload(ampel)
    return payload


def _find_existing_direct_chat(org, current_user, other_user):
    existing_chat = ChatDirect.objects.filter(org=org, users=current_user).filter(users=other_user)
    return existing_chat.first()


@login_required
def serve_chat_image(request, image_identifier):
    """Serve a chat image by opaque UUID (members of that chat only).

    Uses DB lookup + stored ``ImageField.path`` — no user-controlled path segments,
    so path traversal is not possible via the URL.
    """
    org = request.user.org
    msg = (
        ChatMessageDirect.objects.filter(
            image_identifier=image_identifier,
            org=org,
            chat__users=request.user,
        ).first()
    )
    if msg is None or not msg.image:
        msg = (
            ChatMessageGroup.objects.filter(
                image_identifier=image_identifier,
                org=org,
                chat__users=request.user,
            ).first()
        )
    if msg is None or not msg.image:
        return HttpResponseNotFound()

    try:
        full_path = Path(msg.image.path)
    except (ValueError, AttributeError):
        return HttpResponseNotFound()

    if not full_path.is_file():
        return HttpResponseNotFound()

    content_type = (
        mimetypes.guess_type(str(full_path))[0] or "application/octet-stream"
    )
    return FileResponse(full_path.open("rb"), content_type=content_type)


@login_required
def chat_list(request):
    chats = ChatDirect.objects.filter(users=request.user)
    groups = ChatGroup.objects.filter(users=request.user)

    conversations = []

    for chat in chats:
        all_chat_messages = ChatMessageDirect.objects.filter(chat=chat).order_by('-created_at')
        
        if not all_chat_messages.exists():
            continue
        
        unread = all_chat_messages.filter(read=False).exclude(user=request.user).count()
        
        conversations.append({
            'type': 'direct',
            'users': chat.users.exclude(pk=request.user.pk),
            'user_identifiers': [u.customuser.get_identifier() for u in chat.users.exclude(pk=request.user.pk)],
            'id': chat.get_identifier(),
            'url': reverse('chat_direct', args=[chat.get_identifier()]),
            'name': ', '.join(
                u.get_full_name() or u.username
                for u in chat.users.exclude(pk=request.user.pk)
            ),
            'unread_count': unread,
            'updated_at': chat.get_last_message(),
        })

    for group in groups:
        unread = ChatMessageGroup.objects.filter(
            chat=group
        ).exclude(read_by=request.user).exclude(user=request.user).count()
        conversations.append({
            'type': 'group',
            'id': group.get_identifier(),
            'url': reverse('chat_group', args=[group.get_identifier()]),
            'name': group.name,
            'subtitle': f"{group.users.count()} Mitglieder",
            'unread_count': unread,
            'updated_at': group.get_last_message(),
        })

    conversations.sort(key=lambda c: c['updated_at'], reverse=True)

    context = {
        'conversations': conversations,
    }
    context = check_organization_context(request, context)
    return render(request, 'chat-list.html', context)


@login_required
def chat_direct(request, identifier):
    try:
        chat = ChatDirect.objects.get(identifier=identifier, org=request.user.org, users=request.user)
    except ChatDirect.DoesNotExist:
        django_messages.error(request, _('Chat nicht gefunden'))
        return redirect('chat_list')

    if request.method == 'POST':
        form = SendDirectMessageForm(request.POST, request.FILES)
        if form.is_valid():
            msg = ChatMessageDirect.objects.create(
                chat=chat,
                user=request.user,
                org=request.user.org,
                message=form.cleaned_data["message"],
                image=form.cleaned_data.get("image") or None,
            )

            notify_users_about_new_direct_chat_message.s(msg.id, request.user.id).apply_async(countdown=10)
            for recipient in chat.users.exclude(pk=request.user.pk):
                broadcast_unread_badge_for_user(recipient)

            return redirect(reverse('chat_direct', args=[chat.get_identifier()]))
    else:
        form = SendDirectMessageForm()

    chat_messages = ChatMessageDirect.objects.filter(chat=chat).select_related(
        'user', 'answer_to_ampel'
    ).order_by('created_at')
    for msg in chat_messages.filter(read=False).exclude(user=request.user):
        msg.mark_as_read()
        broadcast_direct_message_read_if_needed(msg, chat)
    broadcast_unread_badge_for_user(request.user)

    initial_ampel = None
    ampel_id = request.GET.get('ampel_id')
    if ampel_id and user_is_ampel_staff(request.user):
        ampel = resolve_ampel(request.user.org, ampel_id)
        if user_can_reply_to_ampel_in_direct_chat(request.user, ampel, chat):
            initial_ampel = ampel

    other_users = chat.users.exclude(pk=request.user.pk)
    context = {
        'chat': chat,
        'chat_messages': chat_messages,
        'form': form,
        'other_users': other_users,
        'initial_ampel': initial_ampel,
    }
    context = check_organization_context(request, context)
    return render(request, 'chat-direct.html', context)


@login_required
def chat_group(request, identifier):
    try:
        chat = ChatGroup.objects.get(identifier=identifier, org=request.user.org, users=request.user)
    except ChatGroup.DoesNotExist:
        django_messages.error(request, _('Chat nicht gefunden'))
        return redirect('chat_list')

    if request.method == 'POST':
        form = SendGroupMessageForm(request.POST, request.FILES)
        if form.is_valid():
            msg = ChatMessageGroup.objects.create(
                chat=chat,
                user=request.user,
                org=request.user.org,
                message=form.cleaned_data["message"],
                image=form.cleaned_data.get("image") or None,
            )
            msg.mark_as_read_by(request.user)

            notify_users_about_new_group_chat_message.s(msg.id, request.user.id).apply_async(countdown=10)
            for recipient in chat.users.exclude(pk=request.user.pk):
                broadcast_unread_badge_for_user(recipient)

            return redirect(reverse('chat_group', args=[chat.get_identifier()]))
    else:
        form = SendGroupMessageForm()

    chat_messages = ChatMessageGroup.objects.filter(chat=chat).order_by('created_at')
    for msg in chat_messages.exclude(user=request.user):
        msg.mark_as_read_by(request.user)
    broadcast_unread_badge_for_user(request.user)

    is_creator = chat.created_by == request.user
    non_members = (
        User.objects.filter(customuser__org=request.user.org)
        .exclude(pk__in=chat.users.values_list('pk', flat=True))
        .exclude(customuser__person_cluster__view='B')
        .select_related('customuser').order_by('customuser__person_cluster', 'first_name', 'last_name')
    )

    context = {
        'chat': chat,
        'chat_messages': chat_messages,
        'form': form,
        'is_creator': is_creator,
        'non_members': non_members,
    }
    context = check_organization_context(request, context)
    return render(request, 'chat-group.html', context)


@login_required
def create_chat_direct(request):
    org = request.user.org
    if request.method == 'POST':
        form = ChatDirectForm(request.POST, org=org, current_user=request.user)
        if form.is_valid():
            selected_users = form.cleaned_data.get('users')
            if selected_users:
                existing_chat = ChatDirect.objects.filter(org=org, users=request.user)
                for user in selected_users:
                    existing_chat = existing_chat.filter(users=user)
                if existing_chat.exists():
                    return redirect(reverse('chat_direct', args=[existing_chat.first().get_identifier()]))
            chat = form.save(commit=False)
            chat.org = org
            chat.save()
            form.save_m2m()
            chat.users.add(request.user)
            return redirect(reverse('chat_direct', args=[chat.get_identifier()]))
        django_messages.error(request, _('Fehler beim Erstellen des Chats'))
    else:
        form = ChatDirectForm(org=org, current_user=request.user)

    context = {
        'form': form,
        'available_users': form.fields['users'].queryset.select_related('customuser'),
    }
    context = check_organization_context(request, context)
    return render(request, 'create-chat-direct.html', context)


@login_required
def get_or_create_chat_for_ampel(request, ampel_id):
    if not user_is_ampel_staff(request.user):
        django_messages.error(request, _('Keine Berechtigung'))
        return redirect('chat_list')

    org = request.user.org
    ampel = get_object_or_404(Ampel2, pk=ampel_id, org=org)
    other_user = ampel.user

    if other_user == request.user:
        django_messages.error(request, _('Du kannst dir selbst keine Nachricht senden.'))
        return redirect('chat_list')

    chat = _find_existing_direct_chat(org, request.user, other_user)
    if chat is None:
        chat = ChatDirect.objects.create(org=org)
        chat.users.add(request.user, other_user)

    return redirect(
        f"{reverse('chat_direct', args=[chat.get_identifier()])}?ampel_id={ampel.id}"
    )


@login_required
def create_chat_group(request):
    from Global.models import PersonCluster
    org = request.user.org
    if request.method == 'POST':
        form = ChatGroupForm(request.POST, org=org, current_user=request.user)
        if form.is_valid():
            chat = form.save(commit=False)
            chat.org = org
            chat.created_by = request.user
            chat.save()
            form.save_m2m()
            chat.users.add(request.user)

            notify_users_about_new_group_chat.s(chat.id, request.user.id).apply_async(countdown=10)

            return redirect(reverse('chat_group', args=[chat.get_identifier()]))
        django_messages.error(request, _('Fehler beim Erstellen des Chats'))
    else:
        form = ChatGroupForm(org=org, current_user=request.user)

    available_users = form.fields['users'].queryset.select_related(
        'customuser', 'customuser__person_cluster'
    )

    # Build cluster → user-pk mapping for JS quick-select
    person_clusters = None
    cluster_members = {}
    if getattr(request.user, 'role', None) == 'O':
        person_clusters = PersonCluster.selectable_for_org(org).exclude(view="B")
        for cluster in person_clusters:
            pks = list(
                available_users.filter(customuser__person_cluster=cluster)
                .values_list('pk', flat=True)
            )
            if pks:
                cluster_members[cluster.pk] = pks

    context = {
        'form': form,
        'available_users': available_users,
        'person_clusters': person_clusters,
        'cluster_members_json': json.dumps(cluster_members),
    }
    context = check_organization_context(request, context)
    return render(request, 'create-chat-group.html', context)


@login_required
@require_POST
def manage_chat_group(request, identifier):
    """AJAX endpoint for rename / add-member / remove-member."""
    try:
        chat = ChatGroup.objects.get(identifier=identifier, org=request.user.org, users=request.user)
    except ChatGroup.DoesNotExist:
        return JsonResponse({'error': _('Chat nicht gefunden')}, status=404)

    if chat.created_by != request.user:
        return JsonResponse({'error': _('Keine Berechtigung')}, status=403)

    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, AttributeError):
        return JsonResponse({'error': _('Ungültige Anfrage')}, status=400)

    action = data.get('action')

    if action == 'rename':
        name = data.get('name', '').strip()
        if not name:
            return JsonResponse({'error': _('Name darf nicht leer sein')}, status=400)
        chat.name = name
        chat.save(update_fields=['name', 'updated_at'])
        return JsonResponse({'ok': True, 'name': chat.name})

    elif action == 'add_member':
        user_id = data.get('user_id')
        try:
            user = User.objects.get(pk=user_id, customuser__org=request.user.org)
            user_identifier = user.customuser.get_identifier()
        except User.DoesNotExist:
            return JsonResponse({'error': _('Benutzer nicht gefunden')}, status=404)
        chat.users.add(user)
        return JsonResponse({
            'ok': True,
            'user_id': user.pk,
            'user_identifier': user_identifier,
            'name': str(user),
        })

    elif action == 'remove_member':
        user_id = data.get('user_id')
        if int(user_id) == request.user.pk:
            return JsonResponse({'error': _('Du kannst dich nicht selbst entfernen')}, status=400)
        try:
            user = User.objects.get(pk=user_id, customuser__org=request.user.org)
            user_identifier = user.customuser.get_identifier()
        except User.DoesNotExist:
            return JsonResponse({'error': _('Benutzer nicht gefunden')}, status=404)
        chat.users.remove(user)
        return JsonResponse({
            'ok': True,
            'user_id': user.pk,
            'user_identifier': user_identifier,
            'name': str(user),
        })

    return JsonResponse({'error': _('Unbekannte Aktion')}, status=400)


@login_required
@require_POST
def delete_chat_group(request, identifier):
    try:
        chat = ChatGroup.objects.get(identifier=identifier, org=request.user.org, users=request.user)
    except ChatGroup.DoesNotExist:
        django_messages.error(request, _('Chat nicht gefunden'))
        return redirect('chat_list')

    if chat.created_by != request.user:
        django_messages.error(request, _('Keine Berechtigung'))
        return redirect(reverse('chat_group', args=[identifier]))

    chat.delete()
    django_messages.success(request, _('Gruppe wurde gelöscht.'))
    return redirect('chat_list')


@login_required
@require_POST
def leave_chat_group(request, identifier):
    try:
        chat = ChatGroup.objects.get(identifier=identifier, org=request.user.org, users=request.user)
    except ChatGroup.DoesNotExist:
        django_messages.error(request, _('Chat nicht gefunden'))
        return redirect('chat_list')

    if chat.created_by == request.user:
        django_messages.error(request, _('Als Ersteller:in kannst du die Gruppe nicht verlassen. Lösche sie stattdessen.'))
        return redirect(reverse('chat_group', args=[identifier]))

    chat.users.remove(request.user)
    django_messages.success(request, _(f'Du hast die Gruppe „{chat.name}" verlassen.'))
    return redirect('chat_list')


@login_required
@require_POST
def send_message_direct(request, identifier):
    try:
        chat = ChatDirect.objects.get(identifier=identifier, org=request.user.org, users=request.user)
    except ChatDirect.DoesNotExist:
        return JsonResponse({'error': _('Chat nicht gefunden')}, status=404)

    image_file = None
    text = ""
    answer_to_ampel_id = None
    content_type = request.content_type or ""
    if request.FILES.get("image") or "multipart/form-data" in content_type:
        text = request.POST.get("message", "").strip()
        image_file = request.FILES.get("image")
        answer_to_ampel_id = request.POST.get("answer_to_ampel_id")
    else:
        try:
            data = json.loads(request.body)
            text = data.get("message", "").strip()
            answer_to_ampel_id = data.get("answer_to_ampel_id")
        except (json.JSONDecodeError, AttributeError, TypeError):
            text = request.POST.get("message", "").strip()
            answer_to_ampel_id = request.POST.get("answer_to_ampel_id")

    if not text and not image_file:
        return JsonResponse({"error": _('Leere Nachricht')}, status=400)

    create_kw = {
        "chat": chat,
        "user": request.user,
        "org": request.user.org,
        "message": text,
    }
    if image_file:
        create_kw["image"] = image_file
    answer_to_ampel = resolve_ampel_for_direct_reply(
        request.user, answer_to_ampel_id, chat
    )
    if answer_to_ampel:
        create_kw["answer_to_ampel"] = answer_to_ampel
    msg = ChatMessageDirect.objects.create(**create_kw)

    notify_users_about_new_direct_chat_message.s(msg.id, request.user.id).apply_async(countdown=10)
    for recipient in chat.users.exclude(pk=request.user.pk):
        broadcast_unread_badge_for_user(recipient)

    payload = _chat_message_payload(msg, request.user, viewer=request.user)
    broadcast_chat_message_to_room(
        "direct",
        chat.get_identifier(),
        _chat_message_payload(msg, request.user, viewer=request.user),
    )
    return JsonResponse(payload)


@login_required
@require_POST
def send_message_group(request, identifier):
    try:
        chat = ChatGroup.objects.get(identifier=identifier, org=request.user.org, users=request.user)
    except ChatGroup.DoesNotExist:
        return JsonResponse({'error': _('Chat nicht gefunden')}, status=404)

    image_file = None
    text = ""
    content_type = request.content_type or ""
    if request.FILES.get("image") or "multipart/form-data" in content_type:
        text = request.POST.get("message", "").strip()
        image_file = request.FILES.get("image")
    else:
        try:
            data = json.loads(request.body)
            text = data.get("message", "").strip()
        except (json.JSONDecodeError, AttributeError, TypeError):
            text = request.POST.get("message", "").strip()

    if not text and not image_file:
        return JsonResponse({"error": _('Leere Nachricht')}, status=400)

    create_kw = {
        "chat": chat,
        "user": request.user,
        "org": request.user.org,
        "message": text,
    }
    if image_file:
        create_kw["image"] = image_file
    msg = ChatMessageGroup.objects.create(**create_kw)
    msg.mark_as_read_by(request.user)

    notify_users_about_new_group_chat_message.s(msg.id, request.user.id).apply_async(countdown=10)
    for recipient in chat.users.exclude(pk=request.user.pk):
        broadcast_unread_badge_for_user(recipient)

    payload = _chat_message_payload(msg, request.user)
    broadcast_chat_message_to_room("group", chat.get_identifier(), payload)
    return JsonResponse(payload)


def _parse_edit_message_body(request):
    try:
        data = json.loads(request.body)
        return data.get("message", "").strip()
    except (json.JSONDecodeError, AttributeError, TypeError):
        return request.POST.get("message", "").strip()


@login_required
@require_POST
def edit_message_direct(request, identifier, message_id):
    try:
        chat = ChatDirect.objects.get(
            identifier=identifier, org=request.user.org, users=request.user
        )
    except ChatDirect.DoesNotExist:
        return JsonResponse({"error": _("Chat nicht gefunden")}, status=404)

    text = _parse_edit_message_body(request)
    if not text:
        return JsonResponse({"error": _("Leere Nachricht")}, status=400)

    try:
        msg = ChatMessageDirect.objects.get(id=message_id, chat=chat)
    except ChatMessageDirect.DoesNotExist:
        return JsonResponse({"error": _("Nachricht nicht gefunden")}, status=404)

    if msg.user_id != request.user.id:
        return JsonResponse({"error": _("Keine Berechtigung")}, status=403)

    if not msg.can_be_edited():
        return JsonResponse(
            {"error": _("Nachricht kann nicht mehr bearbeitet werden")},
            status=403,
        )

    msg.message = text
    msg.is_edited = True
    msg.save(update_fields=["message", "is_edited", "updated_at"])

    broadcast_chat_edit_to_room("direct", chat.get_identifier(), msg.id, msg.message)
    return JsonResponse({"ok": True, "id": msg.id, "message": msg.message})


@login_required
@require_POST
def edit_message_group(request, identifier, message_id):
    try:
        chat = ChatGroup.objects.get(
            identifier=identifier, org=request.user.org, users=request.user
        )
    except ChatGroup.DoesNotExist:
        return JsonResponse({"error": _("Chat nicht gefunden")}, status=404)

    text = _parse_edit_message_body(request)
    if not text:
        return JsonResponse({"error": _("Leere Nachricht")}, status=400)

    try:
        msg = ChatMessageGroup.objects.get(id=message_id, chat=chat)
    except ChatMessageGroup.DoesNotExist:
        return JsonResponse({"error": _("Nachricht nicht gefunden")}, status=404)

    if msg.user_id != request.user.id:
        return JsonResponse({"error": _("Keine Berechtigung")}, status=403)

    if not msg.can_be_edited():
        return JsonResponse(
            {"error": _("Nachricht kann nicht mehr bearbeitet werden")},
            status=403,
        )

    msg.message = text
    msg.is_edited = True
    msg.save(update_fields=["message", "is_edited", "updated_at"])

    broadcast_chat_edit_to_room("group", chat.get_identifier(), msg.id, msg.message)
    return JsonResponse({"ok": True, "id": msg.id, "message": msg.message})


@login_required
def ajax_chat_poll(request):
    n = get_unread_chat_message_count(request.user)
    return JsonResponse({'number_of_unread_messages': n})


@login_required
def ajax_chat_list_updates(request):
    chats = ChatDirect.objects.filter(users=request.user)
    groups = ChatGroup.objects.filter(users=request.user)

    data = []
    for chat in chats:
        data.append({
            'type': 'direct',
            'id': chat.get_identifier(),
            'unread_count': ChatMessageDirect.objects.filter(
                chat=chat, read=False
            ).exclude(user=request.user).count(),
        })
    for group in groups:
        data.append({
            'type': 'group',
            'id': group.get_identifier(),
            'unread_count': ChatMessageGroup.objects.filter(
                chat=group
            ).exclude(read_by=request.user).exclude(user=request.user).count(),
        })
    return JsonResponse({'conversations': data})


@login_required
def ajax_chat_updates(request, chat_type, chat_id):
    last_id = int(request.GET.get('last_id', 0))

    try:
        if chat_type == 'direct':
            chat = ChatDirect.objects.get(identifier=chat_id, org=request.user.org, users=request.user)
            new_messages = ChatMessageDirect.objects.filter(
                chat=chat, id__gt=last_id
            ).order_by('id').select_related('user', 'answer_to_ampel')
            data = [_chat_message_payload(m, m.user, viewer=request.user) for m in new_messages]

            for m in new_messages:
                m.mark_as_read()
                broadcast_direct_message_read_if_needed(m, chat)
        elif chat_type == 'group':
            chat = ChatGroup.objects.get(identifier=chat_id, org=request.user.org, users=request.user)
            new_messages = ChatMessageGroup.objects.filter(
                chat=chat, id__gt=last_id
            ).order_by('id').select_related('user')
            data = [_chat_message_payload(m, m.user, viewer=request.user) for m in new_messages]
            for m in new_messages:
                m.mark_as_read_by(request.user)
        else:
            return JsonResponse({'error': _('Ungültiger Chat-Typ')}, status=400)
    except (ChatDirect.DoesNotExist, ChatGroup.DoesNotExist):
        return JsonResponse({'error': _('Chat nicht gefunden')}, status=404)

    if data:
        broadcast_unread_badge_for_user(request.user)

    return JsonResponse({'messages': data})
