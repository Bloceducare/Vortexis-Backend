from rest_framework import status
from rest_framework.response import Response
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import IsAuthenticated
from accounts.permissions import IsOrganizer, IsAdmin
from .serializers import (
    OrganizationSerializer, CreateOrganizationSerializer,
    UpdateOrganizationSerializer, AddModeratorSerializer,
    RemoveModeratorSerializer
)
from .models import Organization
from drf_yasg.utils import swagger_auto_schema

class CreateOrganizationView(GenericAPIView):
    serializer_class = CreateOrganizationSerializer
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        request_body=serializer_class,
        responses={201: OrganizationSerializer, 400: 'Bad Request'},
        operation_description="Create a new organization.",
        tags=['organization']
    )
    def post(self, request):
        serializer = self.get_serializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        organization = serializer.save()
        return Response(OrganizationSerializer(organization).data, status=status.HTTP_201_CREATED)

class UpdateOrganizationView(GenericAPIView):
    serializer_class = UpdateOrganizationSerializer
    permission_classes = [IsAuthenticated, IsOrganizer]

    @swagger_auto_schema(
        request_body=serializer_class,
        responses={200: OrganizationSerializer, 404: 'Not Found'},
        operation_description="Update an organization.",
        tags=['organization']
    )
    def put(self, request, organization_id):
        try:
            organization = Organization.objects.get(id=organization_id)
        except Organization.DoesNotExist:
            return Response({'error': 'Organization not found.'}, status=status.HTTP_404_NOT_FOUND)
        serializer = self.get_serializer(organization, data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        organization = serializer.save()
        return Response(OrganizationSerializer(organization).data)

class DeleteOrganizationView(GenericAPIView):
    permission_classes = [IsAuthenticated, IsOrganizer]

    @swagger_auto_schema(
        responses={204: 'No Content', 403: 'Forbidden', 404: 'Not Found'},
        operation_description="Delete an organization.",
        tags=['organization']
    )
    def delete(self, request, organization_id):
        try:
            organization = Organization.objects.get(id=organization_id)
        except Organization.DoesNotExist:
            return Response({'error': 'Organization not found.'}, status=status.HTTP_404_NOT_FOUND)
        if organization.organizer != request.user:
            return Response({'error': 'Not authorized.'}, status=status.HTTP_403_FORBIDDEN)
        organization.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

class GetOrganizationView(GenericAPIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        responses={200: OrganizationSerializer, 404: 'Not Found'},
        operation_description="Retrieve an organization by ID.",
        tags=['organization']
    )
    def get(self, request, organization_id):
        try:
            organization = Organization.objects.get(id=organization_id)
        except Organization.DoesNotExist:
            return Response({'error': 'Organization not found.'}, status=status.HTTP_404_NOT_FOUND)
        return Response(OrganizationSerializer(organization).data)

class GetOrganizationsView(GenericAPIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        responses={200: OrganizationSerializer(many=True)},
        operation_description="Retrieve all organizations.",
        tags=['organization']
    )
    def get(self, request):
        organizations = Organization.objects.all()
        return Response(OrganizationSerializer(organizations, many=True).data)

class GetUnapprovedOrganizationsView(GenericAPIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    @swagger_auto_schema(
        responses={200: OrganizationSerializer(many=True)},
        operation_description="Retrieve all unapproved organizations.",
        tags=['organization']
    )
    def get(self, request):
        organizations = Organization.objects.filter(is_approved=False)
        return Response(OrganizationSerializer(organizations, many=True).data)

class ApproveOrganizationView(GenericAPIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    @swagger_auto_schema(
        responses={200: OrganizationSerializer, 404: 'Not Found'},
        operation_description="Approve an organization.",
        tags=['organization']
    )
    def post(self, request, organization_id):
        try:
            organization = Organization.objects.get(id=organization_id)
        except Organization.DoesNotExist:
            return Response({'error': 'Organization not found.'}, status=status.HTTP_404_NOT_FOUND)
        organization.is_approved = True
        organization.save()
        organizer = organization.organizer
        if organizer:
            organizer.is_organizer = True
            organizer.save()
            # Send approval email
            from django.core.mail import send_mail
            send_mail(
                subject='Organization Approved',
                message=f'Your organization "{organization.name}" has been approved.',
                from_email='noreply@hackathon.com',
                recipient_list=[organizer.email],
                fail_silently=True
            )
        return Response(OrganizationSerializer(organization).data)

class AddModeratorView(GenericAPIView):
    serializer_class = AddModeratorSerializer
    permission_classes = [IsAuthenticated, IsOrganizer]

    @swagger_auto_schema(
        request_body=serializer_class,
        responses={200: OrganizationSerializer, 404: 'Not Found'},
        operation_description="Add moderators to an organization.",
        tags=['organization']
    )
    def post(self, request, organization_id):
        try:
            organization = Organization.objects.get(id=organization_id)
        except Organization.DoesNotExist:
            return Response({'error': 'Organization not found.'}, status=status.HTTP_404_NOT_FOUND)
        serializer = self.get_serializer(organization, data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        organization = serializer.save()
        return Response(OrganizationSerializer(organization).data)

class RemoveModeratorView(GenericAPIView):
    serializer_class = RemoveModeratorSerializer
    permission_classes = [IsAuthenticated, IsOrganizer]

    @swagger_auto_schema(
        request_body=serializer_class,
        responses={200: OrganizationSerializer, 404: 'Not Found'},
        operation_description="Remove moderators from an organization.",
        tags=['organization']
    )
    def post(self, request, organization_id):
        try:
            organization = Organization.objects.get(id=organization_id)
        except Organization.DoesNotExist:
            return Response({'error': 'Organization not found.'}, status=status.HTTP_404_NOT_FOUND)
        serializer = self.get_serializer(organization, data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        organization = serializer.save()
        return Response(OrganizationSerializer(organization).data)