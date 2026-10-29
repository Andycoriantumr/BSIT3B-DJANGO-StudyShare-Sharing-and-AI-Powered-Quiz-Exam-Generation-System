from .models import Conversation


def recent_conversations(user, limit=6):
    conversations = Conversation.objects.filter(user=user)
    pinned = conversations.filter(is_pinned=True).order_by('-updated_at')
    recent = conversations.filter(is_pinned=False).order_by('-updated_at')[:limit]
    return [*pinned, *recent]
