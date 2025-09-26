from django.db import transaction, models
from django.db.models import Q
from rest_framework import viewsets, mixins, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Conversation, ConversationParticipant, Message
from .serializers import (
    ConversationSerializer,
    ConversationParticipantSerializer,
    MessageSerializer,
    CreateDMSerializer,
    CreateTeamConversationSerializer,
    CreateJudgesConversationSerializer,
)


class ConversationViewSet(viewsets.ModelViewSet):
    queryset = Conversation.objects.all()
    serializer_class = ConversationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return Conversation.objects.none()

        user = self.request.user
        if not user.is_authenticated:
            return Conversation.objects.none()

        return Conversation.objects.filter(participants__user=user).distinct()

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=False, methods=['post'], url_path='dm')
    def create_dm(self, request):
        serializer = CreateDMSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        target_user_id = serializer.validated_data['user_id']
        user = request.user
        if target_user_id == user.id:
            return Response({"detail": "Cannot create DM with yourself."}, status=status.HTTP_400_BAD_REQUEST)

        # Check if a DM already exists between the two users
        existing = Conversation.objects.filter(
            type='dm',
            participants__user_id__in=[user.id, target_user_id]
        ).annotate(num_participants=models.Count('participants')).filter(num_participants=2).first()

        if existing:
            return Response(ConversationSerializer(existing).data)

        with transaction.atomic():
            conv = Conversation.objects.create(type='dm', created_by=user)
            ConversationParticipant.objects.bulk_create([
                ConversationParticipant(conversation=conv, user=user, is_admin=True),
                ConversationParticipant(conversation=conv, user_id=target_user_id, is_admin=False),
            ])
        return Response(ConversationSerializer(conv).data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['post'], url_path='team')
    def create_team_conversation(self, request):
        from team.models import Team
        serializer = CreateTeamConversationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        team_id = serializer.validated_data['team_id']
        user = request.user

        team = Team.objects.select_related('hackathon').prefetch_related('members').get(id=team_id)
        if not team.members.filter(id=user.id).exists() and team.organizer_id != user.id:
            return Response({"detail": "Not authorized for this team."}, status=status.HTTP_403_FORBIDDEN)

        conv, created = Conversation.objects.get_or_create(type='team', team=team, defaults={
            'created_by': user,
            'hackathon': team.hackathon,
            'title': f"Team: {team.name}",
        })

        if created:
            ConversationParticipant.objects.bulk_create([
                ConversationParticipant(conversation=conv, user=member, is_admin=(member.id == team.organizer_id))
                for member in team.members.all()
            ])
            if team.organizer_id and not team.members.filter(id=team.organizer_id).exists():
                ConversationParticipant.objects.create(conversation=conv, user_id=team.organizer_id, is_admin=True)

        return Response(ConversationSerializer(conv).data, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)

    @action(detail=False, methods=['post'], url_path='judges')
    def create_judges_conversation(self, request):
        from hackathon.models import Hackathon
        from organization.models import Organization
        serializer = CreateJudgesConversationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        hackathon_id = serializer.validated_data['hackathon_id']
        include_organizers = serializer.validated_data['include_organizers']
        include_org_members = serializer.validated_data['include_org_members']

        user = request.user
        hackathon = Hackathon.objects.select_related('organization').prefetch_related('judges').get(id=hackathon_id)

        # Authorization: judges or organizers of this hackathon/org
        is_judge = hackathon.judges.filter(id=user.id).exists()
        is_organizer = False
        if hackathon.organization and (hackathon.organization.organizer_id == user.id or hackathon.organization.moderators.filter(id=user.id).exists()):
            is_organizer = True
        if not (is_judge or is_organizer):
            return Response({"detail": "Not authorized to create judges conversation."}, status=status.HTTP_403_FORBIDDEN)

        conv, created = Conversation.objects.get_or_create(
            type='judges', hackathon=hackathon,
            defaults={'created_by': user, 'organization': hackathon.organization}
        )

        if created:
            participants = set(hackathon.judges.values_list('id', flat=True))
            if include_organizers and hackathon.organization and hackathon.organization.organizer_id:
                participants.add(hackathon.organization.organizer_id)
            if include_org_members and hackathon.organization:
                participants.update(hackathon.organization.moderators.values_list('id', flat=True))

            ConversationParticipant.objects.bulk_create([
                ConversationParticipant(conversation=conv, user_id=uid, is_admin=True if uid == hackathon.organization.organizer_id else False)
                for uid in participants
            ])

        return Response(ConversationSerializer(conv).data, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


class MessageViewSet(mixins.CreateModelMixin, mixins.ListModelMixin, viewsets.GenericViewSet):
    serializer_class = MessageSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        conversation_id = self.kwargs.get('conversation_pk')
        qs = Message.objects.select_related('conversation').filter(conversation_id=conversation_id)
        # Ensure user is participant
        if not ConversationParticipant.objects.filter(conversation_id=conversation_id, user=user).exists():
            return Message.objects.none()
        return qs

    def perform_create(self, serializer):
        conversation_id = self.kwargs.get('conversation_pk')
        user = self.request.user
        if not ConversationParticipant.objects.filter(conversation_id=conversation_id, user=user, can_post=True).exists():
            raise PermissionError("You are not allowed to post in this conversation.")
        serializer.save(sender=user, conversation_id=conversation_id)

