import json
import uuid

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST

from apps.notes.models import Subject
from apps.users.guests import display_identity

from .models import ChatQuizAttempt, Conversation, Message, MessageAttachment
from .services import (
    generate_attachment_questions,
    generate_reply,
    grade_attachment_quiz,
    normalize_question_count,
)
from .selectors import recent_conversations

MAX_ATTACHMENT_COUNT = 5
MAX_ATTACHMENT_SIZE = 10 * 1024 * 1024
ALLOWED_FILE_EXTENSIONS = {'.pdf', '.txt', '.md', '.csv', '.docx'}
ATTACHMENT_CONTENT_TYPES = {
    '.pdf': 'application/pdf',
    '.txt': 'text/plain; charset=utf-8',
    '.md': 'text/markdown; charset=utf-8',
    '.csv': 'text/csv; charset=utf-8',
    '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
}


class ChatAttachmentError(ValueError):
    pass


def _chat_attachments(request):
    uploads = []
    for upload in request.FILES.getlist('files'):
        name = (upload.name or '').replace('\\', '/').rsplit('/', 1)[-1]
        extension = '.' + name.rsplit('.', 1)[-1].lower() if '.' in name else ''
        if extension not in ALLOWED_FILE_EXTENSIONS:
            raise ChatAttachmentError(
                f'{name or "This file"} has an unsupported type.'
            )
        if not upload.size or upload.size > MAX_ATTACHMENT_SIZE:
            raise ChatAttachmentError(
                f'{name} must be smaller than 10 MB and cannot be empty.'
            )
        uploads.append({
            'kind': MessageAttachment.KIND_FILE,
            'upload': upload,
            'name': name[:255],
            'content_type': ATTACHMENT_CONTENT_TYPES.get(
                extension, upload.content_type or 'application/octet-stream'
            ),
        })

    if len(uploads) > MAX_ATTACHMENT_COUNT:
        raise ChatAttachmentError('Attach no more than 5 files per message.')
    return uploads


def _store_chat_attachments(message, attachments):
    for attachment in attachments:
        MessageAttachment.objects.create(
            message=message,
            kind=attachment['kind'],
            original_name=attachment['name'],
            content_type=attachment['content_type'],
            file=attachment['upload'],
        )


def _serve_chat_attachment(request, pk, as_attachment):
    attachment = get_object_or_404(
        MessageAttachment.objects.select_related('message__conversation'),
        pk=pk,
        message__conversation__user=request.user,
    )
    extension = (
        '.' + attachment.original_name.rsplit('.', 1)[-1].lower()
        if '.' in attachment.original_name else ''
    )
    content_type = ATTACHMENT_CONTENT_TYPES.get(
        extension, 'application/octet-stream'
    )
    response = FileResponse(
        attachment.file.open('rb'),
        as_attachment=as_attachment,
        filename=attachment.original_name or 'uploaded-file',
        content_type=content_type,
    )
    response['X-Content-Type-Options'] = 'nosniff'
    return response


@login_required(login_url='login')
@require_GET
def view_attachment(request, pk):
    return _serve_chat_attachment(request, pk, as_attachment=False)


@login_required(login_url='login')
@require_GET
def download_attachment(request, pk):
    return _serve_chat_attachment(request, pk, as_attachment=True)


@login_required(login_url='login')
@require_POST
def delete_attachment(request, pk):
    attachment = get_object_or_404(
        MessageAttachment,
        pk=pk,
        message__conversation__user=request.user,
    )
    name = attachment.original_name or 'Uploaded file'
    attachment.file.delete(save=False)
    attachment.delete()
    messages.success(request, f'"{name}" was deleted.')
    return redirect('notes:note_list')


def _attachment_error_response(request, error, redirect_url):
    if _wants_json(request):
        return JsonResponse({'ok': False, 'error': str(error)}, status=400)
    messages.error(request, str(error))
    return redirect(redirect_url)


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
        'has_quiz': bool(message.quiz_data),
        'created_at': message.created_at.isoformat(),
    }


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


def _safe_attachment_questions(message, question_count):
    try:
        return generate_attachment_questions(
            message, num_questions=question_count
        )
    except Exception:
        return {
            'content': (
                'Sorry — something went wrong while generating questions '
                'from that file. Please try again.'
            ),
            'provider': 'local',
            'questions': [],
        }


def _assistant_message(conversation, reply):
    return Message.objects.create(
        conversation=conversation,
        role=Message.ROLE_ASSISTANT,
        content=reply['content'],
        provider=reply.get('provider', ''),
        quiz_data=reply.get('questions') or [],
    )


def _conversation_title(content, attachments):
    if content:
        return _title_from(content)
    if attachments:
        return _title_from(f'Questions from {attachments[0]["name"]}')
    return 'New chat'


@login_required(login_url='login')
def chat_home(request):
    return redirect('dashboard')


@login_required(login_url='login')
@require_POST
def start_chat(request):
    content = (request.POST.get('content') or '').strip()
    try:
        attachments = _chat_attachments(request)
    except ChatAttachmentError as error:
        return _attachment_error_response(request, error, 'dashboard')

    if not content and not attachments:
        if _wants_json(request):
            return JsonResponse(
                {'ok': False, 'error': 'Type a question or attach a file to start a chat.'},
                status=400,
            )
        messages.error(request, 'Type a question or attach a file to start a chat.')
        return redirect('dashboard')

    content = content or 'Generate practice questions from the attached file.'
    think = request.POST.get('think') == '1'
    question_count = normalize_question_count(
        request.POST.get('question_count')
    )
    conversation = Conversation.objects.create(
        user=request.user, title=_conversation_title(
            (request.POST.get('content') or '').strip(), attachments
        )
    )
    user_message = Message.objects.create(
        conversation=conversation,
        role=Message.ROLE_USER,
        content=content,
    )
    _store_chat_attachments(user_message, attachments)
    if attachments:
        reply = _safe_attachment_questions(user_message, question_count)
    else:
        reply = _safe_reply(request.user, conversation, content, think=think)
    assistant = _assistant_message(conversation, reply)
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
    chat_messages = list(
        conversation.messages.prefetch_related('attachments').all()
    )
    display_name, initials = display_identity(request.user)
    return render(request, 'chat/detail.html', {
        'conversation': conversation,
        'chat_messages': chat_messages,
        'sidebar_conversations': recent_conversations(request.user),
        'sidebar_subjects': Subject.objects.filter(is_active=True).order_by('name')[:3],
        'active_conversation': conversation,
        'display_name': display_name,
        'initials': initials,
    })


@login_required(login_url='login')
@require_POST
def toggle_pin_conversation(request, pk):
    conversation = get_object_or_404(Conversation, pk=pk, user=request.user)
    conversation.is_pinned = not conversation.is_pinned
    conversation.save(update_fields=['is_pinned'])
    action = 'pinned' if conversation.is_pinned else 'unpinned'
    messages.success(request, f'Chat {action}.')
    return redirect('chat:detail', pk=conversation.pk)


@login_required(login_url='login')
@require_POST
def share_conversation(request, pk):
    conversation = get_object_or_404(Conversation, pk=pk, user=request.user)
    if conversation.share_token is None:
        conversation.share_token = uuid.uuid4()
        conversation.save(update_fields=['share_token'])
    share_url = request.build_absolute_uri(
        reverse('chat:shared_conversation', args=[conversation.share_token])
    )
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({'ok': True, 'share_url': share_url})
    messages.success(request, 'The public chat link is ready to copy.')
    return redirect('chat:detail', pk=conversation.pk)


@login_required(login_url='login')
@require_POST
def revoke_conversation_share(request, pk):
    conversation = get_object_or_404(Conversation, pk=pk, user=request.user)
    conversation.share_token = None
    conversation.save(update_fields=['share_token'])
    messages.success(request, 'The public chat link has been disabled.')
    return redirect('chat:detail', pk=conversation.pk)


@login_required(login_url='login')
@require_POST
def delete_conversation(request, pk):
    conversation = get_object_or_404(Conversation, pk=pk, user=request.user)
    for attachment in MessageAttachment.objects.filter(
        message__conversation=conversation
    ):
        attachment.file.delete(save=False)
    conversation.delete()
    messages.success(request, 'Chat deleted.')
    return redirect('dashboard')


@require_GET
def shared_conversation(request, token):
    conversation = get_object_or_404(
        Conversation.objects.prefetch_related('messages'),
        share_token=token,
    )
    response = render(
        request, 'chat/shared_conversation.html', {'conversation': conversation}
    )
    response['Cache-Control'] = 'no-store'
    return response


@login_required(login_url='login')
def quiz_attempt_detail(request, pk):
    attempt = get_object_or_404(
        ChatQuizAttempt.objects.select_related(
            'message__conversation',
        ),
        pk=pk,
        taker=request.user,
    )
    result = grade_attachment_quiz(
        attempt.message.quiz_data,
        attempt.answers,
    )
    return render(request, 'chat/quiz_attempt.html', {
        'attempt': attempt,
        'result': result,
    })


@login_required(login_url='login')
@require_POST
def send_message(request, pk):
    conversation = get_object_or_404(
        Conversation, pk=pk, user=request.user
    )
    content = (request.POST.get('content') or '').strip()
    try:
        attachments = _chat_attachments(request)
    except ChatAttachmentError as error:
        return _attachment_error_response(
            request, error, reverse('chat:detail', args=[conversation.pk])
        )

    if not content and not attachments:
        if _wants_json(request):
            return JsonResponse(
                {'ok': False, 'error': 'Type a message or attach a file first.'},
                status=400,
            )
        messages.error(request, 'Type a message or attach a file first.')
        return redirect('chat:detail', pk=conversation.pk)

    user_content = content
    content = content or 'Generate practice questions from the attached file.'
    think = request.POST.get('think') == '1'
    question_count = normalize_question_count(
        request.POST.get('question_count')
    )
    user_message = Message.objects.create(
        conversation=conversation,
        role=Message.ROLE_USER,
        content=content,
    )
    _store_chat_attachments(user_message, attachments)
    if attachments:
        reply = _safe_attachment_questions(user_message, question_count)
    else:
        reply = _safe_reply(request.user, conversation, content, think=think)
    assistant = _assistant_message(conversation, reply)
    if conversation.title == 'New chat':
        conversation.title = _conversation_title(user_content, attachments)
    conversation.save(update_fields=['title', 'updated_at'])

    if _wants_json(request):
        return JsonResponse({
            'ok': True,
            'title': conversation.title,
            'reply': _serialize_message(assistant),
        })
    return redirect('chat:detail', pk=conversation.pk)


@login_required(login_url='login')
@require_POST
def grade_message_quiz(request, pk):
    message = get_object_or_404(
        Message,
        pk=pk,
        role=Message.ROLE_ASSISTANT,
        conversation__user=request.user,
    )
    if not message.quiz_data:
        return JsonResponse(
            {'ok': False, 'error': 'This message has no quiz to grade.'},
            status=400,
        )
    try:
        payload = json.loads(request.body.decode('utf-8') or '{}')
    except (UnicodeDecodeError, ValueError):
        return JsonResponse(
            {'ok': False, 'error': 'Invalid quiz submission.'},
            status=400,
        )
    answers = payload.get('answers') if isinstance(payload, dict) else None
    if not isinstance(answers, (dict, list)):
        return JsonResponse(
            {'ok': False, 'error': 'Answers must be sent as a list or object.'},
            status=400,
        )
    result = grade_attachment_quiz(message.quiz_data, answers)
    ChatQuizAttempt.objects.create(
        message=message,
        taker=request.user,
        score=result['score'],
        total=result['total'],
        percentage=result['percent'],
        answers=answers,
    )
    return JsonResponse({'ok': True, **result})
