from rest_framework import status
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import PermissionDenied
from rest_framework.generics import GenericAPIView
from django.core.mail import send_mail
from django.conf import settings
from .serializers import CreateTeamSerializer, TeamSerializer, UpdateTeamSerializer, AddMemberSerializer, RemoveMemberSerializer, CreateHackathonTeamSerializer
from .models import Team
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

# Create your views here.

class TeamViewSet(ModelViewSet):
    queryset = Team.objects.all()
    permission_classes = [IsAuthenticated]
    
    def get_serializer_class(self):
        if self.action == 'create':
            return CreateTeamSerializer
        elif self.action in ['update', 'partial_update']:
            return UpdateTeamSerializer
        return TeamSerializer
    
    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return Team.objects.none()
        # Return teams where user is a member or organizer
        return Team.objects.filter(members=self.request.user).distinct()
    
    def perform_create(self, serializer):
        serializer.save()
    
    def perform_destroy(self, instance):
        if instance.organizer != self.request.user:
            raise PermissionDenied("You are not authorized to delete this team.")
        instance.delete()
    
    @action(detail=True, methods=['post'], serializer_class=AddMemberSerializer)
    def add_member(self, request, pk=None):
        """Add a member to the team"""
        team = self.get_object()
        serializer = AddMemberSerializer(team, data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({'team': TeamSerializer(team).data}, status=status.HTTP_200_OK)
    
    @action(detail=True, methods=['post'], serializer_class=RemoveMemberSerializer)
    def remove_member(self, request, pk=None):
        """Remove a member from the team"""
        team = self.get_object()
        serializer = RemoveMemberSerializer(team, data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({'team': TeamSerializer(team).data}, status=status.HTTP_200_OK)
    
    @swagger_auto_schema(
        manual_parameters=[
            openapi.Parameter(
                'hackathon_id',
                openapi.IN_QUERY,
                description='The ID of the hackathon to get the user\'s team for',
                type=openapi.TYPE_INTEGER,
                required=True
            )
        ],
        responses={
            200: TeamSerializer,
            400: "Bad Request - hackathon_id parameter required",
            404: "Not Found - No team found for this hackathon"
        },
        operation_description="Get the team that the authenticated user is part of for a specific hackathon",
        tags=['teams']
    )
    @action(detail=False, methods=['get'])
    def by_hackathon(self, request):
        """Get user's team for a specific hackathon"""
        hackathon_id = request.query_params.get('hackathon_id')
        if not hackathon_id:
            return Response({'error': 'hackathon_id parameter required'}, status=status.HTTP_400_BAD_REQUEST)
        
        team = Team.objects.filter(
            members=request.user, 
            hackathons__id=hackathon_id
        ).first()
        
        if team:
            return Response(TeamSerializer(team).data, status=status.HTTP_200_OK)
        return Response({'message': 'No team found for this hackathon'}, status=status.HTTP_404_NOT_FOUND)


class CreateHackathonTeamView(GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = CreateHackathonTeamSerializer

    @swagger_auto_schema(
        request_body=CreateHackathonTeamSerializer,
        responses={
            201: TeamSerializer,
            400: "Bad Request",
            401: "Unauthorized"
        },
        operation_description="Create a new team for a specific hackathon (all members must be registered for the hackathon).",
        tags=['teams']
    )
    def post(self, request):
        serializer = self.serializer_class(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        team = serializer.save()
        
        hackathon_id = request.data.get('hackathon_id')
        from hackathon.models import Hackathon
        hackathon = Hackathon.objects.get(id=hackathon_id)
        
        # Send email notifications to all team members
        send_mail(
            subject=f"Team Created for {hackathon.title}",
            message=f"Dear Team,\n\nA new team '{team.name}' has been created for '{hackathon.title}'.\nTeam Organizer: {team.organizer.get_full_name if team.organizer else 'Unknown'}\nMembers: {', '.join([member.get_full_name for member in team.members.all()])}\n\nGood luck with the hackathon!",
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[member.email for member in team.members.all()],
            fail_silently=True
        )
        
        return Response(
            {"message": "Team created successfully for hackathon.", "team": TeamSerializer(team).data},
            status=status.HTTP_201_CREATED
        )
