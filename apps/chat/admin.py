from django.contrib import admin

from .models import Conversation, Message


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ('title', 'user', 'created_at', 'updated_at')
    search_fields = ('title', 'user__username')
    list_filter = ('created_at',)
    raw_id_fields = ('user',)


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('conversation', 'role', 'provider', 'created_at')
    search_fields = ('content', 'conversation__title', 'conversation__user__username')
    list_filter = ('role', 'provider', 'created_at')
    raw_id_fields = ('conversation',)
