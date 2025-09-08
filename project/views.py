from django.shortcuts import render
from rest_framework import status
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from .serializers import CreateProjectSerializer, ProjectSerializer, UpdateProjectSerializer
from .models import Project

# Create your views here.

class ProjectViewSet(ModelViewSet):
    permission_classes = [IsAuthenticated]
    
    def get_serializer_class(self):
        if self.action == 'create':
            return CreateProjectSerializer
        elif self.action in ['update', 'partial_update']:
            return UpdateProjectSerializer
        return ProjectSerializer
    
    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return Project.objects.none()
        return Project.objects.filter(team__members=self.request.user)
    
    def perform_create(self, serializer):
        serializer.save()
    
    @swagger_auto_schema(
        manual_parameters=[
            openapi.Parameter(
                'hackathon_id',
                openapi.IN_QUERY,
                description='The ID of the hackathon to get the user\'s project for',
                type=openapi.TYPE_INTEGER,
                required=True
            )
        ],
        responses={
            200: ProjectSerializer,
            400: "Bad Request - hackathon_id parameter required",
            404: "Not Found - No project found for this hackathon"
        },
        operation_description="Get the project that the authenticated user's team submitted to a specific hackathon",
        tags=['projects']
    )
    @action(detail=False, methods=['get'])
    def by_hackathon(self, request):
        """Get user's team project for a specific hackathon"""
        from hackathon.models import Hackathon, Submission
        from team.models import Team
        
        hackathon_id = request.query_params.get('hackathon_id')
        if not hackathon_id:
            return Response(
                {'error': 'hackathon_id parameter is required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            hackathon_id = int(hackathon_id)
            hackathon = Hackathon.objects.get(id=hackathon_id)
        except (ValueError, Hackathon.DoesNotExist):
            return Response(
                {'error': 'Invalid hackathon_id or hackathon does not exist'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Find the user's team for this hackathon
        user_team = Team.objects.filter(
            members=request.user, 
            hackathon__id=hackathon_id
        ).first()
        
        if not user_team:
            return Response(
                {'error': 'You are not part of any team registered for this hackathon'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Find the submission (and thus project) for this team and hackathon
        try:
            submission = Submission.objects.get(
                hackathon=hackathon,
                team=user_team
            )
            project = submission.project
            
            return Response(
                ProjectSerializer(project).data, 
                status=status.HTTP_200_OK
            )
            
        except Submission.DoesNotExist:
            return Response(
                {'error': 'No project has been submitted by your team for this hackathon'}, 
                status=status.HTTP_404_NOT_FOUND
            )
