from rest_framework import status
from rest_framework.response import Response
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import IsAuthenticated
from accounts.permissions import IsOrganizer, IsAdmin
from .serializers import OrganizationSerializer
from .models import Organization
from drf_yasg.utils import swagger_auto_schema

# Create your views here.

class CreateOrganizationView(GenericAPIView):
    serializer_class = OrganizationSerializer.CreateOrganizationSerializer
    permission_classes = [IsAuthenticated]
    @swagger_auto_schema(
        request_body=serializer_class,
        responses={201: 'Organization created successfully', 400: 'Bad Request'},
        operation_description="Create a new organization.",
        tags=['organization']
    )
    def post(self, request):
        serializer = self.serializer_class(data=request.data, context={'request': request})
        if serializer.is_valid(raise_exception=True):
            organization = serializer.save()
            return Response({'organization': OrganizationSerializer.OrganizationSerializer(organization).data}, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
class AddModeratorView(GenericAPIView):
    serializer_class = OrganizationSerializer.AddModeratorSerializer
    permission_classes = [IsAuthenticated, IsOrganizer]
    @swagger_auto_schema(
        request_body=serializer_class,
        responses={200: 'Moderator added successfully', 400: 'Bad Request'},
        operation_description="Add a moderator to an organization.",
        tags=['organization']
    )
    def post(self, request, organization_id):
        try:
            organization = Organization.objects.get(id=organization_id)
        except Organization.DoesNotExist:
            return Response({'error': 'Organization does not exist.'}, status=status.HTTP_404_NOT_FOUND)
        serializer = self.serializer_class(organization, data=request.data, context={'request': request})
        if serializer.is_valid(raise_exception=True):
            serializer.save()
            return Response({'organization': OrganizationSerializer.OrganizationSerializer(organization).data}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
class GetOrganizationsView(GenericAPIView):
    permission_classes = [IsAuthenticated]
    @swagger_auto_schema(
        responses={200: 'Organizations retrieved successfully', 400: 'Bad Request'},
        operation_description="Get all organizations.",
        tags=['organization']
    )
    def get(self, request):
        organizations = Organization.objects.all()
        return Response({'organizations': OrganizationSerializer.OrganizationSerializer(organizations, many=True).data}, status=status.HTTP_200_OK)
    
class GetOrganizationView(GenericAPIView):
    permission_classes = [IsAuthenticated]
    @swagger_auto_schema(
        responses={200: 'Organization retrieved successfully', 400: 'Bad Request'},
        operation_description="Get an organization.",
        tags=['organization']
    )
    def get(self, request, organization_id):
        try:
            organization = Organization.objects.get(id=organization_id)
        except Organization.DoesNotExist:
            return Response({'error': 'Organization does not exist.'}, status=status.HTTP_404_NOT_FOUND)
        return Response({'organization': OrganizationSerializer.OrganizationSerializer(organization).data}, status=status.HTTP_200_OK)
    
class ApproveOrganizationView(GenericAPIView):
    permission_classes = [IsAuthenticated, IsAdmin]
    serializer_class = OrganizationSerializer.OrganizationSerializer
    @swagger_auto_schema(
        responses={200: 'Organization approved successfully', 400: 'Bad Request'},
        operation_description="Approve an organization.",
        tags=['organization']
    )
    def post(self, request, organization_id):
        try:
            organization = Organization.objects.get(id=organization_id)
        except Organization.DoesNotExist:
            return Response({'error': 'Organization does not exist.'}, status=status.HTTP_404_NOT_FOUND)
        organization.is_approved = True
        organization.save()
        organizer = organization.organizer
        organizer.is_organizer = True
        organizer.save()
        return Response({'organization': OrganizationSerializer.OrganizationSerializer(organization).data}, status=status.HTTP_200_OK)
    
class UpdateOrganizationView(GenericAPIView):
    serializer_class = OrganizationSerializer.UpdateOrganizationSerializer
    permission_classes = [IsAuthenticated]
    @swagger_auto_schema(
        request_body=serializer_class,
        responses={200: 'Organization updated successfully', 400: 'Bad Request'},
        operation_description="Update an organization.",
        tags=['organization']
    )
    def put(self, request, organization_id):
        try:
            organization = Organization.objects.get(id=organization_id)
        except Organization.DoesNotExist:
            return Response({'error': 'Organization does not exist.'}, status=status.HTTP_404_NOT_FOUND)
        serializer = self.serializer_class(organization, data=request.data, context={'request': request})
        if serializer.is_valid(raise_exception=True):
            serializer.save()
            return Response({'organization': OrganizationSerializer.OrganizationSerializer(organization).data}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
class DeleteOrganizationView(GenericAPIView):
    permission_classes = [IsAuthenticated]
    @swagger_auto_schema(
        responses={204: 'Organization deleted successfully', 400: 'Bad Request'},
        operation_description="Delete an organization.",
        tags=['organization']
    )
    def delete(self, request, organization_id):
        organization = Organization.objects.get(id=organization_id)
        if organization.organizer != request.user:
            return Response({'error': 'You are not authorized to delete this organization.'}, status=status.HTTP_403_FORBIDDEN)
        organization.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)