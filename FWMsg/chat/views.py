import json

from django.contrib import messages as django_messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from Global.views import check_organization_context

from .forms import ChatDirectForm, ChatGroupForm, SendDirectMessageForm, SendGroupMessageForm
from .models import ChatDirect, ChatGroup, ChatMessageDirect, ChatMessageGroup
from .tasks import notify_users_about_new_direct_chat_message, notify_users_about_new_group_chat_message, notify_users_about_new_group_chat


@login_required
def chat_list(request):
    chats = ChatDirect.objects.filter(users=request.user)
    groups = ChatGroup.objects.filter(users=request.user)

    conversations = []

    for chat in chats:
        unread = ChatMessageDirect.objects.filter(
            chat=chat, read=False
        ).exclude(user=request.user).count()
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
        django_messages.error(request, 'Chat nicht gefunden')
        return redirect('chat_list')

    if request.method == 'POST':
        form = SendDirectMessageForm(request.POST)
        if form.is_valid():
            msg = ChatMessageDirect.objects.create(
                chat=chat,
                user=request.user,
                org=request.user.org,
                message=form.cleaned_data['message'],
            )
            
            notify_users_about_new_direct_chat_message.s(msg.id, request.user.id).apply_async(countdown=10)
                
            return redirect(reverse('chat_direct', args=[chat.get_identifier()]))
    else:
        form = SendDirectMessageForm()

    chat_messages = ChatMessageDirect.objects.filter(chat=chat).order_by('created_at')
    for msg in chat_messages.filter(read=False).exclude(user=request.user):
        msg.mark_as_read()
        
    other_users = chat.users.exclude(pk=request.user.pk)
    context = {
        'chat': chat,
        'chat_messages': chat_messages,
        'form': form,
        'other_users': other_users,
    }
    context = check_organization_context(request, context)
    return render(request, 'chat-direct.html', context)


@login_required
def chat_group(request, identifier):
    try:
        chat = ChatGroup.objects.get(identifier=identifier, org=request.user.org, users=request.user)
    except ChatGroup.DoesNotExist:
        django_messages.error(request, 'Chat nicht gefunden')
        return redirect('chat_list')

    if request.method == 'POST':
        form = SendGroupMessageForm(request.POST)
        if form.is_valid():
            msg = ChatMessageGroup.objects.create(
                chat=chat,
                user=request.user,
                org=request.user.org,
                message=form.cleaned_data['message'],
            )
            msg.mark_as_read_by(request.user)
            
            notify_users_about_new_group_chat_message.s(msg.id, request.user.id).apply_async(countdown=10)
                
            return redirect(reverse('chat_group', args=[chat.get_identifier()]))
    else:
        form = SendGroupMessageForm()

    chat_messages = ChatMessageGroup.objects.filter(chat=chat).order_by('created_at')
    for msg in chat_messages.exclude(user=request.user):
        msg.mark_as_read_by(request.user)

    context = {
        'chat': chat,
        'chat_messages': chat_messages,
        'form': form,
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
        django_messages.error(request, 'Fehler beim Erstellen des Chats')
    else:
        form = ChatDirectForm(org=org, current_user=request.user)

    context = {
        'form': form,
        'available_users': form.fields['users'].queryset.select_related('customuser'),
    }
    context = check_organization_context(request, context)
    return render(request, 'create-chat-direct.html', context)


@login_required
def create_chat_group(request):
    org = request.user.org
    if request.method == 'POST':
        form = ChatGroupForm(request.POST, org=org, current_user=request.user)
        if form.is_valid():
            chat = form.save(commit=False)
            chat.org = org
            chat.save()
            form.save_m2m()
            chat.users.add(request.user)
            
            notify_users_about_new_group_chat.s(chat.id, request.user.id).apply_async(countdown=10)
            
            return redirect(reverse('chat_group', args=[chat.get_identifier()]))
        django_messages.error(request, 'Fehler beim Erstellen des Chats')
    else:
        form = ChatGroupForm(org=org, current_user=request.user)

    context = {'form': form}
    context = check_organization_context(request, context)
    return render(request, 'create-chat-group.html', context)


@login_required
@require_POST
def send_message_direct(request, identifier):
    try:
        chat = ChatDirect.objects.get(identifier=identifier, org=request.user.org, users=request.user)
    except ChatDirect.DoesNotExist:
        return JsonResponse({'error': 'Chat nicht gefunden'}, status=404)

    try:
        data = json.loads(request.body)
        text = data.get('message', '').strip()
    except (json.JSONDecodeError, AttributeError):
        text = request.POST.get('message', '').strip()

    if not text:
        return JsonResponse({'error': 'Leere Nachricht'}, status=400)

    msg = ChatMessageDirect.objects.create(
        chat=chat,
        user=request.user,
        org=request.user.org,
        message=text,
    )
    
    notify_users_about_new_direct_chat_message.s(msg.id, request.user.id).apply_async(countdown=10)
    
    return JsonResponse({
        'id': msg.id,
        'user': str(request.user),
        'user_id': request.user.id,
        'message': msg.message,
        'created_at': msg.created_at.strftime('%d.%m.%Y %H:%M'),
    })


@login_required
@require_POST
def send_message_group(request, identifier):
    try:
        chat = ChatGroup.objects.get(identifier=identifier, org=request.user.org, users=request.user)
    except ChatGroup.DoesNotExist:
        return JsonResponse({'error': 'Chat nicht gefunden'}, status=404)

    try:
        data = json.loads(request.body)
        text = data.get('message', '').strip()
    except (json.JSONDecodeError, AttributeError):
        text = request.POST.get('message', '').strip()

    if not text:
        return JsonResponse({'error': 'Leere Nachricht'}, status=400)

    msg = ChatMessageGroup.objects.create(
        chat=chat,
        user=request.user,
        org=request.user.org,
        message=text,
    )
    msg.mark_as_read_by(request.user)
    
    notify_users_about_new_group_chat_message.s(msg.id, request.user.id).apply_async(countdown=10)
        
    return JsonResponse({
        'id': msg.id,
        'user': str(request.user),
        'user_id': request.user.id,
        'message': msg.message,
        'created_at': msg.created_at.strftime('%d.%m.%Y %H:%M'),
    })


@login_required
def ajax_chat_poll(request):
    number_of_unread_messages = ChatMessageDirect.objects.filter(chat__users=request.user, read=False).exclude(user=request.user).count() + ChatMessageGroup.objects.filter(chat__users=request.user).exclude(read_by=request.user).exclude(user=request.user).count()
    return JsonResponse({'number_of_unread_messages': number_of_unread_messages})


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
            ).order_by('id').select_related('user')
            data = [
                {
                    'id': m.id,
                    'user': str(m.user),
                    'user_id': m.user.id,
                    'message': m.message,
                    'created_at': m.created_at.strftime('%d.%m.%Y %H:%M'),
                }
                for m in new_messages
            ]
            
            for m in new_messages:
                m.mark_as_read()
        elif chat_type == 'group':
            chat = ChatGroup.objects.get(identifier=chat_id, org=request.user.org, users=request.user)
            new_messages = ChatMessageGroup.objects.filter(
                chat=chat, id__gt=last_id
            ).order_by('id').select_related('user')
            data = [
                {
                    'id': m.id,
                    'user': str(m.user),
                    'user_id': m.user.id,
                    'message': m.message,
                    'created_at': m.created_at.strftime('%d.%m.%Y %H:%M'),
                }
                for m in new_messages
            ]
            for m in new_messages:
                m.mark_as_read_by(request.user)
        else:
            return JsonResponse({'error': 'Ungültiger Chat-Typ'}, status=400)
    except (ChatDirect.DoesNotExist, ChatGroup.DoesNotExist):
        return JsonResponse({'error': 'Chat nicht gefunden'}, status=404)

    return JsonResponse({'messages': data})
