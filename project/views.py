from django.shortcuts import render
from rest_framework import status
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet
from rest_framework.permissions import IsAuthenticated
from drf_yasg.utils import swagger_auto_schema
from .serializers import ProjectSerializer
from .models import Project

# Create your views here.

class ProjectViewSet(ModelViewSet):
    permission_classes = [IsAuthenticated]
    
    def get_serializer_class(self):
        if self.action == 'create':
            return ProjectSerializer.CreateProjectSerializer
        elif self.action in ['update', 'partial_update']:
            return ProjectSerializer.UpdateProjectSerializer
        return ProjectSerializer.ProjectSerializer
    
    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return Project.objects.none()
        return Project.objects.filter(team__members=self.request.user)
    
    def perform_create(self, serializer):
        serializer.save()
