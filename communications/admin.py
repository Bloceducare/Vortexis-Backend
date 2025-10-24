from django.contrib import admin
from .models import Conversation, ConversationParticipant, Message


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ('id', 'type', 'title', 'team', 'hackathon', 'organization', 'created_by', 'created_at')
    list_filter = ('type', 'created_at')
    search_fields = ('title',)
    readonly_fields = ('created_at', 'updated_at')
    raw_id_fields = ('team', 'hackathon', 'organization', 'created_by')
    date_hierarchy = 'created_at'


@admin.register(ConversationParticipant)
class ConversationParticipantAdmin(admin.ModelAdmin):
    list_display = ('id', 'conversation', 'user', 'is_admin', 'can_post', 'joined_at')
    list_filter = ('is_admin', 'can_post', 'joined_at')
    raw_id_fields = ('conversation', 'user')
    date_hierarchy = 'joined_at'


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('id', 'conversation', 'sender', 'created_at', 'edited_at', 'is_deleted')
    list_filter = ('is_deleted', 'created_at')
    search_fields = ('content', 'sender__username')
    readonly_fields = ('created_at', 'edited_at')
    raw_id_fields = ('conversation', 'sender')
    date_hierarchy = 'created_at'

