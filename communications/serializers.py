from rest_framework import serializers
from .models import Conversation, ConversationParticipant, Message


class ConversationParticipantSerializer(serializers.ModelSerializer):
    user_username = serializers.CharField(source='user.username', read_only=True)

    class Meta:
        model = ConversationParticipant
        fields = ['id', 'user', 'user_username', 'is_admin', 'can_post', 'joined_at']
        read_only_fields = ['id', 'joined_at']


class MessageSerializer(serializers.ModelSerializer):
    sender_username = serializers.CharField(source='sender.username', read_only=True)

    class Meta:
        model = Message
        fields = ['id', 'conversation', 'sender', 'sender_username', 'content', 'created_at', 'edited_at', 'is_deleted']
        read_only_fields = ['id', 'created_at', 'edited_at', 'is_deleted', 'conversation', 'sender']


class ConversationSerializer(serializers.ModelSerializer):
    participants = ConversationParticipantSerializer(many=True, read_only=True)
    last_message = serializers.SerializerMethodField()
    unread_count = serializers.SerializerMethodField()

    class Meta:
        model = Conversation
        fields = ['id', 'type', 'title', 'team', 'hackathon', 'organization', 'created_by', 'created_at', 'updated_at', 'participants', 'last_message', 'unread_count']
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_last_message(self, obj):
        # Use prefetched data if available to avoid N+1 queries
        if hasattr(obj, '_prefetched_last_message_list'):
            messages = obj._prefetched_last_message_list
            last_msg = messages[0] if messages else None
            return MessageSerializer(last_msg).data if last_msg else None

        last_msg = obj.messages.select_related('sender').order_by('-created_at').first()
        return MessageSerializer(last_msg).data if last_msg else None

    def get_unread_count(self, obj):
        # This will be implemented when we add read receipts
        return 0


class CreateDMSerializer(serializers.Serializer):
    user_id = serializers.IntegerField(min_value=1)

    def validate_user_id(self, value):
        from accounts.models import User
        if not User.objects.filter(id=value).exists():
            raise serializers.ValidationError("User not found")
        return value


class CreateTeamConversationSerializer(serializers.Serializer):
    team_id = serializers.IntegerField(min_value=1)

    def validate_team_id(self, value):
        from team.models import Team
        if not Team.objects.filter(id=value).exists():
            raise serializers.ValidationError("Team not found")
        return value


class CreateJudgesConversationSerializer(serializers.Serializer):
    hackathon_id = serializers.IntegerField(min_value=1)
    include_organizers = serializers.BooleanField(default=True)
    include_org_members = serializers.BooleanField(default=True)

    def validate_hackathon_id(self, value):
        from hackathon.models import Hackathon
        if not Hackathon.objects.filter(id=value).exists():
            raise serializers.ValidationError("Hackathon not found")
        return value

