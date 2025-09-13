from django.contrib import admin
from .models import Conversation, ConversationParticipant, Message


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ('id', 'type', 'title', 'team', 'hackathon', 'organization', 'created_by', 'created_at')
    list_filter = ('type',)
    search_fields = ('title',)


@admin.register(ConversationParticipant)
class ConversationParticipantAdmin(admin.ModelAdmin):
    list_display = ('id', 'conversation', 'user', 'is_admin', 'can_post', 'joined_at')
    list_filter = ('is_admin', 'can_post')


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('id', 'conversation', 'sender', 'created_at', 'is_deleted')
    list_filter = ('is_deleted',)
    search_fields = ('content',)

