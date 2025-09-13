from rest_framework.permissions import BasePermission
from .models import ConversationParticipant


class IsConversationParticipant(BasePermission):
    def has_object_permission(self, request, view, obj):
        if hasattr(obj, 'participants'):
            return ConversationParticipant.objects.filter(conversation=obj, user=request.user).exists()
        if hasattr(obj, 'conversation_id'):
            return ConversationParticipant.objects.filter(conversation_id=obj.conversation_id, user=request.user).exists()
        return False

