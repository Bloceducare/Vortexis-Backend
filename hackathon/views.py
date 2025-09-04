from rest_framework import status
from rest_framework.response import Response
from rest_framework.generics import GenericAPIView, ListCreateAPIView, RetrieveUpdateDestroyAPIView
from rest_framework.viewsets import ModelViewSet
from rest_framework.permissions import IsAuthenticated
from accounts.permissions import IsOrganizer, IsJudge
from accounts.serializers import UserSerializer
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from drf_yasg.utils import swagger_auto_schema
from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser, FormParser
from drf_yasg import openapi

from team.models import Team
from team.serializers import TeamSerializer
from .models import Hackathon, Theme, Submission, Review, HackathonParticipant
from .serializers import (
    HackathonSerializer, CreateHackathonSerializer, SubmitProjectSerializer, UpdateHackathonSerializer,
    RegisterHackathonSerializer, ThemeSerializer,
    SubmissionSerializer, CreateSubmissionSerializer, UpdateSubmissionSerializer,
    ReviewSerializer, InviteJudgeSerializer, IndividualRegistrationSerializer,
    HackathonParticipantSerializer, JoinTeamSerializer, AcceptJudgeInvitationSerializer
)


class HackathonCreateView(GenericAPIView):
    permission_classes = [IsAuthenticated, IsOrganizer]
    serializer_class = CreateHackathonSerializer
    parser_classes = (MultiPartParser, FormParser)

    @swagger_auto_schema(
        request_body=CreateHackathonSerializer,
        manual_parameters=[
            openapi.Parameter(
                'banner_image',
                openapi.IN_FORM,
                description="Banner image file",
                type=openapi.TYPE_FILE
            ),
        ],
        responses={
            201: HackathonSerializer,
            400: "Bad Request",
            401: "Unauthorized"
        },
        operation_description="Create a new hackathon (organizers with approved organizations only).",
        tags=['hackathons']
    )
    def post(self, request):
        serializer = self.serializer_class(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        hackathon = serializer.save()
        # Send email notification to organizer
        send_mail(
            subject="Hackathon Created Successfully",
            message=f"Dear {request.user.get_full_name},\n\nYour hackathon '{hackathon.title}' has been created successfully.\nDetails: {hackathon.description}\nVenue: {hackathon.venue}\nStart Date: {hackathon.start_date}\nEnd Date: {hackathon.end_date}",
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[request.user.email],
            fail_silently=True
        )
        return Response(
            {"message": "Hackathon created successfully.", "hackathon": HackathonSerializer(hackathon).data},
            status=status.HTTP_201_CREATED
        )


class HackathonListView(ListCreateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = HackathonSerializer

    def get_queryset(self):
        return Hackathon.objects.filter(visibility=True)  # Only show public hackathons

    @swagger_auto_schema(
        responses={
            200: HackathonSerializer(many=True),
            401: "Unauthorized"
        },
        operation_description="List all public hackathons.",
        tags=['hackathons']
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class HackathonRetrieveView(RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = HackathonSerializer
    lookup_field = 'id'
    lookup_url_kwarg = 'hackathon_id'

    def get_queryset(self):
        return Hackathon.objects.all()

    @swagger_auto_schema(
        responses={
            200: HackathonSerializer,
            404: "Hackathon not found",
            401: "Unauthorized"
        },
        operation_description="Retrieve a hackathon's details.",
        tags=['hackathons']
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @swagger_auto_schema(
        request_body=UpdateHackathonSerializer,
        responses={
            200: HackathonSerializer,
            400: "Bad Request",
            403: "Forbidden",
            404: "Hackathon not found"
        },
        operation_description="Update a hackathon (organizers or moderators only).",
        tags=['hackathons']
    )
    def put(self, request, *args, **kwargs):
        return super().put(request, *args, **kwargs)

    @swagger_auto_schema(
        responses={
            204: "Hackathon deleted successfully",
            403: "Forbidden",
            404: "Hackathon not found"
        },
        operation_description="Delete a hackathon (organizers or moderators only).",
        tags=['hackathons']
    )
    def delete(self, request, *args, **kwargs):
        hackathon = self.get_object()
        if hackathon.organization.organizer != request.user and request.user not in hackathon.organization.moderators.all():
            return Response({"error": "You are not authorized to delete this hackathon."}, status=status.HTTP_403_FORBIDDEN)
        hackathon.delete()
        # Send email notification to organizer
        send_mail(
            subject="Hackathon Deleted",
            message=f"Dear {request.user.get_full_name},\n\nYour hackathon '{hackathon.title}' has been deleted.",
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[request.user.email],
            fail_silently=True
        )
        return Response({"message": "Hackathon deleted successfully."}, status=status.HTTP_204_NO_CONTENT)


class HackathonRegistrationView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        responses={
            201: HackathonParticipantSerializer,
            400: "Bad Request",
            401: "Unauthorized",
            404: "Hackathon not found"
        },
        operation_description="Register authenticated user for a hackathon. After registration, user can create or join teams.",
        tags=['hackathons']
    )
    def post(self, request, hackathon_id):
        try:
            hackathon = Hackathon.objects.get(id=hackathon_id)
        except Hackathon.DoesNotExist:
            return Response({"error": "Hackathon does not exist."}, status=status.HTTP_404_NOT_FOUND)
        
        # Check if registration deadline has passed
        if hackathon.submission_deadline and timezone.now() > hackathon.submission_deadline:
            return Response({"error": "Registration deadline has passed."}, status=status.HTTP_400_BAD_REQUEST)
        
        # Check if user is already registered
        if HackathonParticipant.objects.filter(hackathon=hackathon, user=request.user).exists():
            return Response({"error": "You are already registered for this hackathon."}, status=status.HTTP_400_BAD_REQUEST)
        
        # Create participant record
        participant = HackathonParticipant.objects.create(
            hackathon=hackathon,
            user=request.user,
            looking_for_team=True
        )
        
        # Send email notification
        send_mail(
            subject="Hackathon Registration Successful",
            message=f"Dear {request.user.get_full_name},\n\nYou have been successfully registered for '{hackathon.title}'.\nYou can now join existing teams or create a new team.\nStart Date: {hackathon.start_date}\nEnd Date: {hackathon.end_date}",
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[request.user.email],
            fail_silently=True
        )
        
        return Response(
            {"message": "Successfully registered for hackathon.", "participant": HackathonParticipantSerializer(participant).data},
            status=status.HTTP_201_CREATED
        )


class InviteJudgeView(GenericAPIView):
    permission_classes = [IsAuthenticated, IsOrganizer]
    serializer_class = InviteJudgeSerializer

    @swagger_auto_schema(
        request_body=serializer_class,
        responses={
            200: "Judge invited successfully",
            400: "Bad Request",
            403: "Forbidden",
            404: "Hackathon not found"
        },
        operation_description="Invite a judge to a hackathon (organizers only).",
        tags=['hackathons']
    )
    def post(self, request, hackathon_id):
        try:
            hackathon = Hackathon.objects.get(id=hackathon_id)
        except Hackathon.DoesNotExist:
            return Response({"error": "Hackathon does not exist."}, status=status.HTTP_404_NOT_FOUND)
        if hackathon.organization.organizer != request.user and request.user not in hackathon.organization.moderators.all():
            return Response({"error": "You are not authorized to invite judges for this hackathon."}, status=status.HTTP_403_FORBIDDEN)
        serializer = self.serializer_class(data=request.data, context={'request': request, 'hackathon': hackathon})
        serializer.is_valid(raise_exception=True)
        emails = serializer.validated_data['emails']
        
        # Create judge invitations for all emails
        from .models import JudgeInvitation
        from accounts.utils import send_judge_invitation_email
        
        successful_invitations = []
        failed_invitations = []
        
        for email in emails:
            try:
                invitation = JudgeInvitation.objects.create(
                    hackathon=hackathon,
                    email=email,
                    invited_by=request.user
                )
                
                # Send email notification with invitation link
                send_judge_invitation_email(email, hackathon, invitation.token, request)
                successful_invitations.append(email)
                
            except Exception as e:
                failed_invitations.append({
                    'email': email,
                    'error': str(e)
                })
        
        response_data = {
            "message": f"Judge invitations processed. {len(successful_invitations)} successful, {len(failed_invitations)} failed.",
            "successful_invitations": successful_invitations,
            "total_sent": len(successful_invitations)
        }
        
        if failed_invitations:
            response_data["failed_invitations"] = failed_invitations
        
        return Response(response_data, status=status.HTTP_200_OK)


class AcceptJudgeInvitationView(GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = AcceptJudgeInvitationSerializer

    @swagger_auto_schema(
        request_body=serializer_class,
        responses={
            200: "Judge invitation accepted successfully",
            400: "Bad Request",
            403: "Forbidden", 
            404: "Invitation not found"
        },
        operation_description="Accept a judge invitation using the invitation token.",
        tags=['hackathons']
    )
    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        invitation = serializer.validated_data['token']
        
        # Check if the user's email matches the invitation email
        if request.user.email != invitation.email:
            return Response(
                {"error": "This invitation was not sent to your email address."}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Set user as judge if not already
        if not request.user.is_judge:
            request.user.is_judge = True
            request.user.save()
        
        # Add user as judge to the hackathon
        invitation.hackathon.judges.add(request.user)
        
        # Mark invitation as accepted
        invitation.is_accepted = True
        invitation.accepted_at = timezone.now()
        invitation.save()
        
        return Response({
            "message": "Judge invitation accepted successfully.",
            "hackathon": {
                "id": invitation.hackathon.id,
                "title": invitation.hackathon.title
            }
        }, status=status.HTTP_200_OK)


class SubmitProjectView(GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = SubmitProjectSerializer

    @swagger_auto_schema(
        request_body=serializer_class,
        responses={
            201: SubmissionSerializer,
            400: "Bad Request",
            401: "Unauthorized",
            404: "Project or Hackathon not found"
        },
        operation_description="Submit a project to a hackathon.",
        tags=['projects']
    )
    def post(self, request, project_id):
        from project.models import Project
        try:
            project = Project.objects.get(id=project_id)
        except Project.DoesNotExist:
            return Response({"error": "Project does not exist."}, status=status.HTTP_404_NOT_FOUND)
        if project.team not in request.user.teams.all():
            return Response({"error": "You are not a member of this project's team."}, status=status.HTTP_403_FORBIDDEN)
        serializer = self.serializer_class(data=request.data, context={'request': request, 'project_id': project_id})
        serializer.is_valid(raise_exception=True)
        submission = serializer.save()
        # Send email notification to team members
        send_mail(
            subject="Project Submission Successful",
            message=f"Dear {request.user.get_full_name},\n\nYour project '{project.title}' has been submitted to '{submission.hackathon.title}'.\nSubmission ID: {submission.id}",
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[member.email for member in project.team.members.all()],
            fail_silently=True
        )
        return Response(
            {"message": "Project submitted successfully.", "submission": SubmissionSerializer(submission).data},
            status=status.HTTP_201_CREATED
        )


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
            return Submission.objects.filter(team__members=self.request.user)
        if self.request.user.is_organizer or self.request.user.is_judge:
            return Submission.objects.filter(hackathon_id=hackathon_id)
        return Submission.objects.filter(hackathon_id=hackathon_id, team__members=self.request.user)

    def get_serializer_context(self):
        context = super().get_serializer_context()
        hackathon_id = self.kwargs.get('hackathon_id')
        if hackathon_id:
            hackathon = Hackathon.objects.get(id=hackathon_id)
            context['hackathon'] = hackathon
        return context

    def perform_create(self, serializer):
        hackathon = Hackathon.objects.get(id=self.kwargs['hackathon_id'])
        serializer.save()
        # Send email notification for submission
        submission = serializer.instance
        send_mail(
            subject="New Submission Received",
            message=f"Dear {hackathon.organization.organizer.get_full_name},\n\nA new submission for '{hackathon.title}' has been received.\nProject: {submission.project.title}\nTeam: {submission.team.name}",
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[hackathon.organization.organizer.email],
            fail_silently=True
        )

    def perform_update(self, serializer):
        submission = serializer.save()
        if submission.approved:
            # Send email notification for approval
            send_mail(
                subject="Submission Approved",
                message=f"Dear {submission.team.members.first().get_full_name},\n\nYour submission '{submission.project.title}' for '{submission.hackathon.title}' has been approved.",
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[member.email for member in submission.team.members.all()],
                fail_silently=True
            )


class ReviewViewSet(ModelViewSet):
    permission_classes = [IsAuthenticated, IsJudge]
    serializer_class = ReviewSerializer

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return Review.objects.none()
        hackathon_id = self.kwargs.get('hackathon_id')
        if not hackathon_id:
            return Review.objects.filter(judge=self.request.user)
        return Review.objects.filter(submission__hackathon_id=hackathon_id, judge=self.request.user)

    def perform_create(self, serializer):
        serializer.save(judge=self.request.user)
        # Update submission status to reviewed
        review = serializer.instance
        submission = review.submission
        if submission.status == 'pending':
            submission.status = 'reviewed'
            submission.save()
        # Send email notification to submission team
        send_mail(
            subject="New Review for Your Submission",
            message=f"Dear {review.submission.team.members.first().get_full_name},\n\nYour submission '{review.submission.project.title}' for '{review.submission.hackathon.title}' has received a new review.\nScore: {review.overall_score}\nComments: {review.review or 'No comments provided'}",
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[member.email for member in review.submission.team.members.all()],
            fail_silently=True
        )


class JudgeAllReviewsView(APIView):
    permission_classes = [IsAuthenticated, IsJudge]

    @swagger_auto_schema(
        responses={
            200: ReviewSerializer(many=True),
            401: "Unauthorized",
            403: "Forbidden"
        },
        operation_description="Get all reviews made by the authenticated judge across all hackathons.",
        tags=['reviews']
    )
    def get(self, request):
        reviews = Review.objects.filter(judge=request.user).select_related('submission__hackathon', 'submission__project', 'submission__team')
        serializer = ReviewSerializer(reviews, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class ThemeViewSet(ModelViewSet):
    permission_classes = [IsAuthenticated, IsOrganizer]
    serializer_class = ThemeSerializer

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return Theme.objects.none()
        hackathon_id = self.kwargs.get('hackathon_id')
        return Theme.objects.filter(hackathons__id=hackathon_id)

    def perform_create(self, serializer):
        hackathon = Hackathon.objects.get(id=self.kwargs['hackathon_id'])
        theme = serializer.save()
        hackathon.themes.add(theme)


class JudgeHackathonsView(APIView):
    permission_classes = [IsAuthenticated, IsJudge]

    @swagger_auto_schema(
        responses={
            200: HackathonSerializer(many=True),
            401: "Unauthorized",
            403: "Forbidden"
        },
        operation_description="Fetch all hackathons a judge is judging.",
        tags=['hackathons']
    )
    def get(self, request):
        hackathons = Hackathon.objects.filter(judges=request.user)
        serializer = HackathonSerializer(hackathons, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class HackathonJudgesView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        responses={
            200: UserSerializer.RetrieveSerializer(many=True),
            401: "Unauthorized",
            404: "Hackathon not found"
        },
        operation_description="Fetch all judges for a hackathon.",
        tags=['hackathons']
    )
    def get(self, request, hackathon_id):
        try:
            hackathon = Hackathon.objects.get(id=hackathon_id)
        except Hackathon.DoesNotExist:
            return Response({"error": "Hackathon does not exist."}, status=status.HTTP_404_NOT_FOUND)
        
        judges = hackathon.judges.all()
        serializer = UserSerializer.RetrieveSerializer(judges, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class HackathonParticipantsView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        responses={
            200: TeamSerializer(many=True),
            401: "Unauthorized",
            404: "Hackathon not found"
        },
        operation_description="Fetch all participants (teams) for a hackathon.",
        tags=['hackathons']
    )
    def get(self, request, hackathon_id):
        try:
            hackathon = Hackathon.objects.get(id=hackathon_id)
        except Hackathon.DoesNotExist:
            return Response({"error": "Hackathon does not exist."}, status=status.HTTP_404_NOT_FOUND)
        
        participants = hackathon.participants.all()
        serializer = TeamSerializer(participants, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class OrganizerHackathonsView(APIView):
    permission_classes = [IsAuthenticated, IsOrganizer]

    @swagger_auto_schema(
        responses={
            200: HackathonSerializer(many=True),
            401: "Unauthorized",
            403: "Forbidden"
        },
        operation_description="Fetch all hackathons hosted by the authenticated organizer.",
        tags=['hackathons']
    )
    def get(self, request):
        if not request.user.organization:
            return Response({"error": "You don't have an organization."}, status=status.HTTP_400_BAD_REQUEST)
        
        hackathons = Hackathon.objects.filter(organization=request.user.organization)
        serializer = HackathonSerializer(hackathons, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)




class JoinTeamView(GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = JoinTeamSerializer

    @swagger_auto_schema(
        request_body=JoinTeamSerializer,
        responses={
            200: HackathonParticipantSerializer,
            400: "Bad Request",
            401: "Unauthorized",
            404: "Hackathon not found"
        },
        operation_description="Join an existing team in a hackathon (must be registered as individual first).",
        tags=['hackathons']
    )
    def post(self, request, hackathon_id):
        try:
            hackathon = Hackathon.objects.get(id=hackathon_id)
        except Hackathon.DoesNotExist:
            return Response({"error": "Hackathon does not exist."}, status=status.HTTP_404_NOT_FOUND)
        
        serializer = self.serializer_class(data=request.data, context={'request': request, 'hackathon': hackathon})
        serializer.is_valid(raise_exception=True)
        participant = serializer.save()
        
        team = Team.objects.get(id=serializer.validated_data['team_id'])
        
        # Send email notification to user and team members
        send_mail(
            subject=f"Joined Team for {hackathon.title}",
            message=f"Dear {request.user.get_full_name()},\n\nYou have successfully joined team '{team.name}' for '{hackathon.title}'.",
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[request.user.email],
            fail_silently=True
        )
        
        # Notify team members
        other_members = team.members.exclude(id=request.user.id)
        if other_members.exists():
            send_mail(
                subject=f"New Team Member Joined - {hackathon.title}",
                message=f"Dear Team,\n\n{request.user.get_full_name()} has joined your team '{team.name}' for '{hackathon.title}'.",
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[member.email for member in other_members],
                fail_silently=True
            )
        
        return Response(
            {"message": f"Successfully joined team '{team.name}'.", "participant": HackathonParticipantSerializer(participant).data},
            status=status.HTTP_200_OK
        )


class HackathonIndividualParticipantsView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        manual_parameters=[
            openapi.Parameter(
                'looking_for_team',
                openapi.IN_QUERY,
                description="Filter participants looking for team (true/false)",
                type=openapi.TYPE_BOOLEAN
            )
        ],
        responses={
            200: HackathonParticipantSerializer(many=True),
            401: "Unauthorized",
            404: "Hackathon not found"
        },
        operation_description="Fetch all individual participants for a hackathon, optionally filter by those looking for teams.",
        tags=['hackathons']
    )
    def get(self, request, hackathon_id):
        try:
            hackathon = Hackathon.objects.get(id=hackathon_id)
        except Hackathon.DoesNotExist:
            return Response({"error": "Hackathon does not exist."}, status=status.HTTP_404_NOT_FOUND)
        
        participants = hackathon.individual_participants.all()
        
        # Filter by looking_for_team if specified
        looking_for_team = request.query_params.get('looking_for_team')
        if looking_for_team is not None:
            looking_for_team_bool = looking_for_team.lower() in ['true', '1']
            participants = participants.filter(looking_for_team=looking_for_team_bool)
        
        serializer = HackathonParticipantSerializer(participants, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class AvailableTeamsView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        responses={
            200: TeamSerializer(many=True),
            401: "Unauthorized",
            404: "Hackathon not found"
        },
        operation_description="Fetch teams in hackathon that have available spots for new members.",
        tags=['hackathons']
    )
    def get(self, request, hackathon_id):
        try:
            hackathon = Hackathon.objects.get(id=hackathon_id)
        except Hackathon.DoesNotExist:
            return Response({"error": "Hackathon does not exist."}, status=status.HTTP_404_NOT_FOUND)
        
        # Get teams registered for this hackathon that have available spots
        available_teams = []
        for team in hackathon.participants.all():
            if team.members.count() < hackathon.max_team_size:
                available_teams.append(team)
        
        serializer = TeamSerializer(available_teams, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class UserRegisteredHackathonsView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        responses={
            200: HackathonSerializer(many=True),
            401: "Unauthorized"
        },
        operation_description="Fetch all hackathons the authenticated user is registered for (either individually or through teams).",
        tags=['hackathons']
    )
    def get(self, request):
        user = request.user
        
        # Get hackathons where user is individually registered
        individual_hackathons = Hackathon.objects.filter(
            individual_participants__user=user
        ).distinct()
        
        # Get hackathons where user's teams are registered
        team_hackathons = Hackathon.objects.filter(
            teams__members=user
        ).distinct()
        
        # Combine and remove duplicates
        all_hackathons = (individual_hackathons | team_hackathons).distinct()
        
        serializer = HackathonSerializer(all_hackathons, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class AllSkillsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        skills = Theme.objects.values_list('name', flat=True)
        return Response({"skills": list(skills)}, status=status.HTTP_200_OK)



