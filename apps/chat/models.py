"""StudyShare AI chat models: saved conversations and their messages."""

from django.conf import settings
from django.db import models


class Conversation(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name='chat_conversations',
        on_delete=models.CASCADE,
    )
    title = models.CharField(max_length=200, default='New chat')
    is_pinned = models.BooleanField(default=False)
    share_token = models.UUIDField(
        null=True, blank=True, unique=True, editable=False
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        return self.title


class Message(models.Model):
    ROLE_USER = 'user'
    ROLE_ASSISTANT = 'assistant'
    ROLE_CHOICES = [
        (ROLE_USER, 'User'),
        (ROLE_ASSISTANT, 'Assistant'),
    ]

    conversation = models.ForeignKey(
        Conversation,
        related_name='messages',
        on_delete=models.CASCADE,
    )
    role = models.CharField(max_length=12, choices=ROLE_CHOICES)
    content = models.TextField()
    provider = models.CharField(max_length=20, blank=True)
    quiz_data = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    PROVIDER_LABELS = {
        'gemini': 'Gemini',
        'openai': 'OpenAI',
        'openrouter': 'OpenRouter',
        'local': 'Offline',
    }

    class Meta:
        ordering = ['created_at', 'id']

    @property
    def provider_label(self):
        if not self.provider:
            return ''
        return self.PROVIDER_LABELS.get(self.provider, self.provider.title())

    def __str__(self):
        return f'{self.get_role_display()} — {self.content[:40]}'


class MessageAttachment(models.Model):
    KIND_FILE = 'file'

    message = models.ForeignKey(
        Message,
        related_name='attachments',
        on_delete=models.CASCADE,
    )
    kind = models.CharField(max_length=8, default=KIND_FILE)
    original_name = models.CharField(max_length=255, blank=True)
    file = models.FileField(upload_to='chat/attachments/%Y/%m/')
    content_type = models.CharField(max_length=120, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.original_name or f'Attachment {self.pk}'


class ChatQuizAttempt(models.Model):
    message = models.ForeignKey(
        Message,
        related_name='quiz_attempts',
        on_delete=models.CASCADE,
    )
    taker = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name='chat_quiz_attempts',
        on_delete=models.CASCADE,
    )
    score = models.PositiveIntegerField(default=0)
    total = models.PositiveIntegerField(default=0)
    percentage = models.FloatField(default=0)
    answers = models.JSONField(default=dict, blank=True)
    submitted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-submitted_at']

    def __str__(self):
        return f'{self.taker} — {self.message.conversation.title} ({self.score}/{self.total})'
