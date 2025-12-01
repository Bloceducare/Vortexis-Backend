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
    
    @swagger_auto_schema(
        operation_description="List projects. If accessed via hackathon endpoint (/hackathons/{id}/projects/), returns projects for that hackathon only.",
        tags=['projects']
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)
    
    @swagger_auto_schema(
        operation_description="Create a project. If accessed via hackathon endpoint (/hackathons/{id}/projects/), automatically associates with that hackathon.",
        tags=['projects']
    )
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)
    
    def get_serializer_class(self):
        if self.action == 'create':
            return CreateProjectSerializer
        elif self.action in ['update', 'partial_update']:
            return UpdateProjectSerializer
        return ProjectSerializer
    
    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return Project.objects.none()
        
        # Base queryset with optimizations
        base_queryset = Project.objects.select_related(
            'team', 'team__organizer', 'hackathon', 'hackathon__organization'
        ).prefetch_related(
            'team__members'
        )
        
        hackathon_id = self.kwargs.get('hackathon_id')
        if hackathon_id:
            # Filter by hackathon and user's teams
            queryset = base_queryset.filter(
                hackathon_id=hackathon_id,
                team__members=self.request.user
            )
        else:
            # Return all projects for user's teams
            queryset = base_queryset.filter(team__members=self.request.user)
        
        return queryset.order_by('-created_at')
    
    def perform_create(self, serializer):
        hackathon_id = self.kwargs.get('hackathon_id')
        if hackathon_id:
            # When creating via hackathon-specific endpoint, set hackathon automatically
            from hackathon.models import Hackathon
            hackathon = Hackathon.objects.get(id=hackathon_id)
            serializer.save(hackathon=hackathon)
        else:
            serializer.save()
    
