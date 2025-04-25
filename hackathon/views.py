from rest_framework import status
from rest_framework.response import Response
from rest_framework.generics import GenericAPIView, ListCreateAPIView, RetrieveUpdateDestroyAPIView
from rest_framework.viewsets import ModelViewSet
from rest_framework.permissions import IsAuthenticated
from accounts.permissions import IsOrganizer, IsAdmin, IsJudge
from .serializers import (
    HackathonSerailizer, ProjectSerializer, ReviewSerializer,
    PrizeSerializer, ThemeSerializer, RuleSerializer, SubmissionSerializer,
    CreateSubmissionSerializer, UpdateSubmissionSerializer
)
from .models import Hackathon, Project, Review, Prize, Theme, Rule, Submission
from drf_yasg.utils import swagger_auto_schema
from django.utils import timezone
from rest_framework import serializers

# Create your views here.
class CreateHackathonView(GenericAPIView):
    serializer_class = HackathonSerailizer.CreateHackathonSerializer
    permission_classes = [IsAuthenticated, IsOrganizer]
    @swagger_auto_schema(
        request_body=serializer_class,
        responses={201: 'Hackathon created successfully', 400: 'Bad Request'},
        operation_description="Create a new hackathon.",
        tags=['hackathon']
    )
    def post(self, request):
        serializer = self.serializer_class(data = request.data, context = {'request': request})
        if serializer.is_valid(raise_exception=True):
            hackathon = serializer.save()
            return Response({'hackathon': HackathonSerailizer.HackathonSerializer(hackathon).data}, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
class GetHackathonsView(GenericAPIView):
    permission_classes = [IsAuthenticated]
    
    @swagger_auto_schema(
        responses={200: 'Hackathons retrieved successfully', 400: 'Bad Request'},
        operation_description="Get all hackathons.",
        tags=['hackathon']
    )
    def get(self, request):
        queryset = Hackathon.objects.all()
        serializer = HackathonSerailizer.HackathonSerializer(queryset, many=True)
        return Response({'hackathons': serializer.data}, status=status.HTTP_200_OK)
    
class GetHackathonView(GenericAPIView):
    permission_classes = [IsAuthenticated]
    @swagger_auto_schema(
        responses={200: 'Hackathon retrieved successfully', 400: 'Bad Request'},
        operation_description="Get a hackathon by id.",
        tags=['hackathon']
    )
    def get(self, request, hackathon_id):
        try:
            hackathon = Hackathon.objects.get(id=hackathon_id)
        except Hackathon.DoesNotExist:
            return Response({'error': 'Hackathon does not exist.'}, status=status.HTTP_404_NOT_FOUND)
        return Response({'hackathon': HackathonSerailizer.HackathonSerializer(hackathon).data}, status=status.HTTP_200_OK)
    
class UpdateHackathonView(GenericAPIView):
    serializer_class = HackathonSerailizer.UpdateHackathonSerializer
    permission_classes = [IsAuthenticated, IsOrganizer]
    @swagger_auto_schema(
        request_body=serializer_class,
        responses={200: 'Hackathon updated successfully', 400: 'Bad Request'},
        operation_description="Update a hackathon.",
        tags=['hackathon']
    )
    def put(self, request, hackathon_id):
        try:
            hackathon = Hackathon.objects.get(id=hackathon_id)
        except Hackathon.DoesNotExist:
            return Response({'error': 'Hackathon does not exist.'}, status=status.HTTP_404_NOT_FOUND)
        serializer = self.serializer_class(hackathon, data=request.data, context={'request': request})
        if serializer.is_valid(raise_exception=True):
            serializer.save()
            return Response({'hackathon': HackathonSerailizer.HackathonSerializer(hackathon).data}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class DeleteHackathonView(GenericAPIView):
    permission_classes = [IsAuthenticated, IsOrganizer]
    @swagger_auto_schema(
        responses={204: 'Hackathon deleted successfully', 400: 'Bad Request'},
        operation_description="Delete a hackathon by id.",
        tags=['hackathon']
    )
    def delete(self, request, hackathon_id):
        try:
            hackathon = Hackathon.objects.get(id=hackathon_id)
        except Hackathon.DoesNotExist:
            return Response({'error': 'Hackathon does not exist.'}, status=status.HTTP_404_NOT_FOUND)
        user = request.user
        if hackathon.organization != user.organization:
            return Response({'error': 'You are not authorized to delete this hackathon.'}, status=status.HTTP_401_UNAUTHORIZED)
        hackathon.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

class RegisterForHackathonView(GenericAPIView):
    serializer_class = HackathonSerailizer.RegisterHackathonSerializer
    permission_classes = [IsAuthenticated]
    @swagger_auto_schema(
        responses={201: 'Registered successfully', 400: 'Bad Request'},
        operation_description="Register for a hackathon by id.",
        tags=['hackathon']
    )
    def post(self, request, hackathon_id):
        try:
            hackathon = Hackathon.objects.get(id=hackathon_id)
        except Hackathon.DoesNotExist:
            return Response({'error': 'Hackathon does not exist.'}, status=status.HTTP_404_NOT_FOUND)
        serializer = self.serializer_class(hackathon, data=request.data, context={'request': request})
        if serializer.is_valid(raise_exception=True):
            serializer.save()
            return Response({'hackathon': HackathonSerailizer.HackathonSerializer(hackathon).data, 'message': 'Registered successfully'}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class SubmitProjectView(GenericAPIView):
    serializer_class = ProjectSerializer.SubmitProjectSerializer
    permission_classes = [IsAuthenticated]
    
    @swagger_auto_schema(
        request_body=serializer_class,
        responses={201: 'Project submitted successfully', 400: 'Bad Request'},
        operation_description="Submit a project to a hackathon.",
        tags=['project']
    )
    def post(self, request, project_id):
        try:
            project = Project.objects.get(id=project_id)
        except Project.DoesNotExist:
            return Response({'error': 'Project does not exist.'}, status=status.HTTP_404_NOT_FOUND)
        
        serializer = self.serializer_class(project, data=request.data, context={'request': request})
        if serializer.is_valid(raise_exception=True):
            submission = serializer.save()
            return Response({
                'submission': SubmissionSerializer(submission).data,
                'message': 'Project submitted successfully'
            }, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class ReviewSubmissionView(GenericAPIView):
    serializer_class = ReviewSerializer
    permission_classes = [IsAuthenticated, IsJudge]
    
    @swagger_auto_schema(
        request_body=serializer_class,
        responses={201: 'Review submitted successfully', 400: 'Bad Request'},
        operation_description="Submit a review for a project submission.",
        tags=['review']
    )
    def post(self, request, submission_id):
        try:
            submission = Submission.objects.get(id=submission_id)
        except Submission.DoesNotExist:
            return Response({'error': 'Submission does not exist.'}, status=status.HTTP_404_NOT_FOUND)
        
        if submission.hackathon not in request.user.judged_hackathons.all():
            return Response({'error': 'You are not authorized to review this submission.'}, 
                          status=status.HTTP_401_UNAUTHORIZED)
        
        serializer = self.serializer_class(data=request.data, context={'request': request})
        if serializer.is_valid(raise_exception=True):
            review = serializer.save(submission=submission, judge=request.user)
            return Response({
                'review': ReviewSerializer(review).data,
                'message': 'Review submitted successfully'
            }, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class PrizeViewSet(ModelViewSet):
    serializer_class = PrizeSerializer
    permission_classes = [IsAuthenticated, IsOrganizer]
    
    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return Prize.objects.none()
        hackathon_id = self.kwargs.get('hackathon_id')
        return Prize.objects.filter(hackathon_id=hackathon_id)
    
    def perform_create(self, serializer):
        hackathon_id = self.kwargs.get('hackathon_id')
        hackathon = Hackathon.objects.get(id=hackathon_id)
        serializer.save(hackathon=hackathon)

class ThemeViewSet(ModelViewSet):
    serializer_class = ThemeSerializer
    permission_classes = [IsAuthenticated, IsOrganizer]
    
    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return Theme.objects.none()
        hackathon_id = self.kwargs.get('hackathon_id')
        return Theme.objects.filter(hackathons__id=hackathon_id)

class RuleViewSet(ModelViewSet):
    serializer_class = RuleSerializer
    permission_classes = [IsAuthenticated, IsOrganizer]
    
    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return Rule.objects.none()
        hackathon_id = self.kwargs.get('hackathon_id')
        return Rule.objects.filter(hackathon_id=hackathon_id)
    
    def perform_create(self, serializer):
        hackathon_id = self.kwargs.get('hackathon_id')
        hackathon = Hackathon.objects.get(id=hackathon_id)
        serializer.save(hackathon=hackathon)

class ProjectViewSet(ModelViewSet):
    serializer_class = ProjectSerializer.ProjectSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return Project.objects.none()
        return Project.objects.filter(team__members=self.request.user)

    def perform_create(self, serializer):
        serializer.save(team=self.request.user.teams.first())

class SubmissionViewSet(ModelViewSet):
    permission_classes = [IsAuthenticated]
    
    def get_serializer_class(self):
        if self.action == 'create':
            return CreateSubmissionSerializer
        elif self.action in ['update', 'partial_update']:
            return UpdateSubmissionSerializer
        return SubmissionSerializer
    
    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return Submission.objects.none()
        
        hackathon_id = self.kwargs.get('hackathon_id')
        if not hackathon_id:
            return Submission.objects.none()
            
        if self.request.user.is_organizer or self.request.user.is_judge:
            return Submission.objects.filter(
                hackathon_id=hackathon_id,
                hackathon__in=self.request.user.judged_hackathons.all()
            )
        return Submission.objects.filter(
            hackathon_id=hackathon_id,
            team__members=self.request.user
        )

class ReviewViewSet(ModelViewSet):
    serializer_class = ReviewSerializer
    permission_classes = [IsAuthenticated, IsJudge]
    
    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return Review.objects.none()
            
        hackathon_id = self.kwargs.get('hackathon_id')
        if not hackathon_id:
            return Review.objects.none()
            
        return Review.objects.filter(
            submission__hackathon_id=hackathon_id,
            judge=self.request.user
        )
    
    def perform_create(self, serializer):
        submission_id = self.request.data.get('submission')
        submission = Submission.objects.get(id=submission_id)
        
        # Check if submission belongs to a hackathon the judge is assigned to
        if submission.hackathon not in self.request.user.judged_hackathons.all():
            raise serializers.ValidationError("You are not authorized to review this submission")
            
        # Check if judge has already reviewed this submission
        if Review.objects.filter(submission=submission, judge=self.request.user).exists():
            raise serializers.ValidationError("You have already reviewed this submission")
            
        serializer.save(judge=self.request.user)