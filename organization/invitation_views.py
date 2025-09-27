from rest_framework import status
from rest_framework.response import Response
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import IsAuthenticated
from accounts.permissions import IsOrganizer, IsOrganizationOrganizer
from .serializers import (
    ModeratorInvitationSerializer, CreateModeratorInvitationSerializer,
    AcceptInvitationSerializer, DeclineInvitationSerializer
)
from .models import Organization, ModeratorInvitation
from drf_yasg.utils import swagger_auto_schema


class CreateModeratorInvitationView(GenericAPIView):
    serializer_class = CreateModeratorInvitationSerializer
    permission_classes = [IsAuthenticated, IsOrganizationOrganizer]

    @swagger_auto_schema(
        request_body=serializer_class,
        responses={201: ModeratorInvitationSerializer, 400: 'Bad Request', 404: 'Not Found'},
        operation_description="Invite a moderator to an organization.",
        tags=['organization']
    )
    def post(self, request, organization_id):
        try:
            organization = Organization.objects.get(id=organization_id)
        except Organization.DoesNotExist:
            return Response({'error': 'Organization not found.'}, status=status.HTTP_404_NOT_FOUND)

        if organization.organizer != request.user:
            return Response({'error': 'Only the organizer can send invitations.'}, status=status.HTTP_403_FORBIDDEN)

        serializer = self.get_serializer(
            data=request.data,
            context={
                'organization_id': organization_id,
                'inviter': request.user
            }
        )
        serializer.is_valid(raise_exception=True)
        invitation = serializer.save()
        return Response(ModeratorInvitationSerializer(invitation).data, status=status.HTTP_201_CREATED)


class GetInvitationView(GenericAPIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        responses={200: ModeratorInvitationSerializer, 404: 'Not Found'},
        operation_description="Get invitation details by token.",
        tags=['organization']
    )
    def get(self, request, token):
        try:
            invitation = ModeratorInvitation.objects.get(token=token)
        except ModeratorInvitation.DoesNotExist:
            return Response({'error': 'Invitation not found.'}, status=status.HTTP_404_NOT_FOUND)

        return Response(ModeratorInvitationSerializer(invitation).data)


class AcceptInvitationView(GenericAPIView):
    serializer_class = AcceptInvitationSerializer
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        request_body=serializer_class,
        responses={200: ModeratorInvitationSerializer, 400: 'Bad Request'},
        operation_description="Accept a moderator invitation.",
        tags=['organization']
    )
    def post(self, request):
        serializer = self.get_serializer(data=request.data, context={'user': request.user})
        serializer.is_valid(raise_exception=True)
        invitation = serializer.save()
        return Response(ModeratorInvitationSerializer(invitation).data)


class DeclineInvitationView(GenericAPIView):
    serializer_class = DeclineInvitationSerializer
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        request_body=serializer_class,
        responses={200: ModeratorInvitationSerializer, 400: 'Bad Request'},
        operation_description="Decline a moderator invitation.",
        tags=['organization']
    )
    def post(self, request):
        serializer = self.get_serializer(data=request.data, context={'user': request.user})
        serializer.is_valid(raise_exception=True)
        invitation = serializer.save()
        return Response(ModeratorInvitationSerializer(invitation).data)


class GetSentInvitationsView(GenericAPIView):
    permission_classes = [IsAuthenticated, IsOrganizationOrganizer]

    @swagger_auto_schema(
        responses={200: ModeratorInvitationSerializer(many=True), 404: 'Not Found'},
        operation_description="Get invitations sent by the organizer for their organization.",
        tags=['organization']
    )
    def get(self, request, organization_id):
        try:
            organization = Organization.objects.get(id=organization_id)
        except Organization.DoesNotExist:
            return Response({'error': 'Organization not found.'}, status=status.HTTP_404_NOT_FOUND)

        if organization.organizer != request.user:
            return Response({'error': 'Only the organizer can view sent invitations.'}, status=status.HTTP_403_FORBIDDEN)

        invitations = ModeratorInvitation.objects.filter(organization=organization)
        return Response(ModeratorInvitationSerializer(invitations, many=True).data)


class GetReceivedInvitationsView(GenericAPIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        responses={200: ModeratorInvitationSerializer(many=True)},
        operation_description="Get invitations received by the authenticated user.",
        tags=['organization']
    )
    def get(self, request):
        from django.db import models
        invitations = ModeratorInvitation.objects.filter(
            models.Q(invitee=request.user) | models.Q(email=request.user.email)
        ).distinct()
        return Response(ModeratorInvitationSerializer(invitations, many=True).data)