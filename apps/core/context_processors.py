"""Template context shared by the StudyShare dark shell."""

from django.conf import settings

PROVIDER_LABELS = {
    'gemini': 'Gemini',
    'openai': 'OpenAI',
    'openrouter': 'OpenRouter',
    'local': 'Offline',
}


def _active_ai_provider():
    """Return the provider chat will prefer, matching apps.chat.services."""
    from apps.notes.services import (
        get_gemini_config,
        get_openai_config,
        get_openrouter_config,
    )

    configured = {
        'gemini': bool(get_gemini_config()[0]),
        'openrouter': bool(get_openrouter_config()[0]),
        'openai': bool(get_openai_config()[0]),
    }
    preferred = (getattr(settings, 'AI_PROVIDER', 'auto') or 'auto').strip().lower()
    if preferred in configured and configured[preferred]:
        return preferred
    for name in ('gemini', 'openrouter', 'openai'):
        if configured[name]:
            return name
    return 'local'


def studyshare_shell(request):
    """Supply sidebar identity, subjects, recent chats, and AI status."""
    user = getattr(request, 'user', None)
    if not user or not user.is_authenticated:
        return {}

    from apps.chat.models import Conversation
    from apps.notes.models import Subject

    display_name = user.get_full_name().strip() or user.username
    initials = (
        ''.join(part[0] for part in display_name.split()[:2]).upper()
        or user.username[:1].upper()
    )
    ai_provider = _active_ai_provider()

    return {
        'display_name': display_name,
        'initials': initials,
        'sidebar_subjects': Subject.objects.filter(is_active=True).order_by('name')[:3],
        'sidebar_conversations': list(
            Conversation.objects.filter(user=user).order_by('-updated_at')[:6]
        ),
        'ai_provider': ai_provider,
        'ai_provider_label': PROVIDER_LABELS[ai_provider],
        'ai_online': ai_provider != 'local',
    }
