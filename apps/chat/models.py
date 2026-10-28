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
