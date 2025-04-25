from rest_framework import status
from rest_framework.response import Response
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import IsAuthenticated
from .serializers import TeamSerializer
from .models import Team
from drf_yasg.utils import swagger_auto_schema

# Create your views here.

class CreateTeamView(GenericAPIView):
    serializer_class = TeamSerializer.CreateTeamSerializer
    permission_classes = [IsAuthenticated]
    @swagger_auto_schema(
        request_body=serializer_class,
        responses={201: 'Team created successfully', 400: 'Bad Request'},
        operation_description="Create a new team.",
        tags=['team']
    )
    def post(self, request):
        serializer = self.serializer_class(data = request.data, context = {'request': request})
        if serializer.is_valid(raise_exception=True):
            team = serializer.save()
            return Response({'team': TeamSerializer.TeamSerializer(team).data}, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
class GetTeamsView(GenericAPIView):
    permission_classes = [IsAuthenticated]
    @swagger_auto_schema(
        responses={200: 'Teams retrieved successfully', 400: 'Bad Request'},
        operation_description="Get all teams.",
        tags=['team']
    )
    def get(self, request):
        teams = Team.objects.all()
        return Response({'teams': TeamSerializer.TeamSerializer(teams, many=True).data}, status=status.HTTP_200_OK)
    
class GetTeamView(GenericAPIView):
    permission_classes = [IsAuthenticated]
    @swagger_auto_schema(
        responses={200: 'Team retrieved successfully', 400: 'Bad Request'},
        operation_description="Get a team by id.",
        tags=['team']
    )
    def get(self, request, team_id):
        try:
            team = Team.objects.get(id=team_id)
        except Team.DoesNotExist:
            return Response({'error': 'Team does not exist.'}, status=status.HTTP_404_NOT_FOUND)
        return Response({'team': TeamSerializer.TeamSerializer(team).data}, status=status.HTTP_200_OK)
    
class UpdateTeamView(GenericAPIView):
    serializer_class = TeamSerializer.UpdateTeamSerializer
    permission_classes = [IsAuthenticated]
    @swagger_auto_schema(
        request_body=serializer_class,
        responses={200: 'Team updated successfully', 400: 'Bad Request'},
        operation_description="Update a team.",
        tags=['team']
    )
    def put(self, request, team_id):
        try:
            team = Team.objects.get(id=team_id)
        except Team.DoesNotExist:
            return Response({'error': 'Team does not exist.'}, status=status.HTTP_404_NOT_FOUND)
        serializer = self.serializer_class(data = request.data, context = {'request': request})
        if serializer.is_valid(raise_exception=True):
            team = serializer.save()
            return Response({'team': TeamSerializer.TeamSerializer(team).data}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
class DeleteTeamView(GenericAPIView):
    permission_classes = [IsAuthenticated]
    @swagger_auto_schema(
        responses={204: 'Team deleted successfully', 400: 'Bad Request'},
        operation_description="Delete a team by id.",
        tags=['team']
    )
    def delete(self, request, team_id):
        try:
            team = Team.objects.get(id=team_id)
        except Team.DoesNotExist:
            return Response({'error': 'Team does not exist.'}, status=status.HTTP_404_NOT_FOUND)
        user = request.user
        if team.organizer != user:
            return Response({'error': 'You are not authorized to delete this team.'}, status=status.HTTP_403_FORBIDDEN)
        team.delete()
        return Response({'success': 'Team deleted successfully'}, status=status.HTTP_204_NO_CONTENT)
    
class AddMemberView(GenericAPIView):
    serializer_class = TeamSerializer.AddMemberSerializer
    permission_classes = [IsAuthenticated]
    @swagger_auto_schema(
        request_body=serializer_class,
        responses={200: 'Member added successfully', 400: 'Bad Request'},
        operation_description="Add a member to a team.",
        tags=['team']
    )
    def post(self, request, team_id):
        try:
            team = Team.objects.get(id=team_id)
        except Team.DoesNotExist:
            return Response({'error': 'Team does not exist.'}, status=status.HTTP_404_NOT_FOUND)
        serializer = self.serializer_class(team, data = request.data, context = {'request': request, 'instance': team})
        if serializer.is_valid(raise_exception=True):
            team = serializer.save()
            return Response({'team': TeamSerializer.TeamSerializer(team).data}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
class RemoveMemberView(GenericAPIView):
    serializer_class = TeamSerializer.RemoveMemberSerializer
    permission_classes = [IsAuthenticated]
    @swagger_auto_schema(
        request_body=serializer_class,
        responses={200: 'Member removed successfully', 400: 'Bad Request'},
        operation_description="Remove a member from a team.",
        tags=['team']
    )
    def post(self, request, team_id):
        try:
            team = Team.objects.get(id=team_id)
        except Team.DoesNotExist:
            return Response({'error': 'Team does not exist.'}, status=status.HTTP_404_NOT_FOUND)
        serializer = self.serializer_class(team, data = request.data, context = {'request': request, 'instance': team})
        if serializer.is_valid(raise_exception=True):
            team = serializer.save()
            return Response({'team': TeamSerializer.TeamSerializer(team).data}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
