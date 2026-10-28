from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from apps.notes.models import Subject

from .models import Conversation, Message
from .services import generate_reply


def _display_identity(user):
    display_name = user.get_full_name().strip() or user.username
    initials = (
        ''.join(part[0] for part in display_name.split()[:2]).upper()
        or user.username[:1].upper()
    )
    return display_name, initials


def _wants_json(request):
    return (
        request.headers.get('x-requested-with') == 'XMLHttpRequest'
        or 'application/json' in request.headers.get('accept', '')
    )


def _title_from(content):
    clean = ' '.join((content or '').split())
    if len(clean) > 60:
        clean = clean[:57].rstrip() + '…'
    return clean or 'New chat'


def _serialize_message(message):
    return {
        'id': message.pk,
        'role': message.role,
        'content': message.content,
        'provider': message.provider,
        'created_at': message.created_at.isoformat(),
    }


def _recent_conversations(user):
    return list(
        Conversation.objects.filter(user=user).order_by('-updated_at')[:6]
    )


def _safe_reply(user, conversation, content, think=False):
    try:
        return generate_reply(user, conversation, content, think=think)
    except Exception:
        return {
            'content': (
                'Sorry — something went wrong while generating that answer. '
                'Please try again.'
            ),
            'provider': 'local',
        }


@login_required(login_url='login')
def chat_home(request):
    return redirect('dashboard')


@login_required(login_url='login')
@require_POST
def start_chat(request):
    content = (request.POST.get('content') or '').strip()
    if not content:
        if _wants_json(request):
            return JsonResponse(
                {'ok': False, 'error': 'Type a question to start a chat.'},
                status=400,
            )
        messages.error(request, 'Type a question to start a chat.')
        return redirect('dashboard')

    think = request.POST.get('think') == '1'
    conversation = Conversation.objects.create(
        user=request.user, title=_title_from(content)
    )
    Message.objects.create(
        conversation=conversation,
        role=Message.ROLE_USER,
        content=content,
    )
    reply = _safe_reply(request.user, conversation, content, think=think)
    assistant = Message.objects.create(
        conversation=conversation,
        role=Message.ROLE_ASSISTANT,
        content=reply['content'],
        provider=reply.get('provider', ''),
    )
    conversation.save(update_fields=['updated_at'])

    if _wants_json(request):
        return JsonResponse({
            'ok': True,
            'conversation': {
                'id': conversation.pk,
                'title': conversation.title,
            },
            'redirect_url': reverse('chat:detail', args=[conversation.pk]),
            'reply': _serialize_message(assistant),
        })
    return redirect('chat:detail', pk=conversation.pk)


@login_required(login_url='login')
def conversation_detail(request, pk):
    conversation = get_object_or_404(
        Conversation, pk=pk, user=request.user
    )
    chat_messages = list(conversation.messages.all())
    display_name, initials = _display_identity(request.user)
    return render(request, 'chat/detail.html', {
        'conversation': conversation,
        'chat_messages': chat_messages,
        'sidebar_conversations': _recent_conversations(request.user),
        'sidebar_subjects': Subject.objects.filter(is_active=True).order_by('name')[:3],
        'active_conversation': conversation,
        'display_name': display_name,
        'initials': initials,
    })


@login_required(login_url='login')
@require_POST
def send_message(request, pk):
    conversation = get_object_or_404(
        Conversation, pk=pk, user=request.user
    )
    content = (request.POST.get('content') or '').strip()
    if not content:
        if _wants_json(request):
            return JsonResponse(
                {'ok': False, 'error': 'Type a message first.'},
                status=400,
            )
        messages.error(request, 'Type a message first.')
        return redirect('chat:detail', pk=conversation.pk)

    think = request.POST.get('think') == '1'
    Message.objects.create(
        conversation=conversation,
        role=Message.ROLE_USER,
        content=content,
    )
    reply = _safe_reply(request.user, conversation, content, think=think)
    assistant = Message.objects.create(
        conversation=conversation,
        role=Message.ROLE_ASSISTANT,
        content=reply['content'],
        provider=reply.get('provider', ''),
    )
    if conversation.title == 'New chat':
        conversation.title = _title_from(content)
    conversation.save(update_fields=['title', 'updated_at'])

    if _wants_json(request):
        return JsonResponse({
            'ok': True,
            'title': conversation.title,
            'reply': _serialize_message(assistant),
        })
    return redirect('chat:detail', pk=conversation.pk)
