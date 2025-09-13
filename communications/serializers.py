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

    class Meta:
        model = Conversation
        fields = ['id', 'type', 'title', 'team', 'hackathon', 'organization', 'created_by', 'created_at', 'updated_at', 'participants', 'last_message']
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_last_message(self, obj):
        last_msg = obj.messages.order_by('-created_at').first()
        return MessageSerializer(last_msg).data if last_msg else None


class CreateDMSerializer(serializers.Serializer):
    user_id = serializers.IntegerField()


class CreateTeamConversationSerializer(serializers.Serializer):
    team_id = serializers.IntegerField()


class CreateJudgesConversationSerializer(serializers.Serializer):
    hackathon_id = serializers.IntegerField()
    include_organizers = serializers.BooleanField(default=True)
    include_org_members = serializers.BooleanField(default=True)

