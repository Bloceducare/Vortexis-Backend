import math
from rest_framework import status
from rest_framework.response import Response
from rest_framework.generics import GenericAPIView, ListCreateAPIView, RetrieveUpdateDestroyAPIView
from rest_framework.viewsets import ModelViewSet
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.pagination import PageNumberPagination
from rest_framework.exceptions import NotFound
from django.db.models import Q
from accounts.models import User
from organization.models import Organization
from accounts.permissions import IsOrganizer, IsJudge
from accounts.serializers import UserSerializer
from django.conf import settings
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from drf_yasg.utils import swagger_auto_schema
from rest_framework.views import APIView
from drf_yasg import openapi
from notifications.services import NotificationService
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


def normalize_hackathon_name(name):
    return name.strip().lower().replace('-', '_').replace(' ', '_')


def get_hackathon_by_name(hackathon_name):
    normalized = normalize_hackathon_name(hackathon_name)

    queryset = Hackathon.objects.select_related(
        'organization', 'organization__organizer'
    ).prefetch_related(
        'themes', 'skills', 'judges'
    )

    for hackathon in queryset:
        if normalize_hackathon_name(hackathon.title) == normalized:
            return hackathon

    title_variant = hackathon_name.replace('_', ' ').replace('-', ' ')
    return queryset.filter(title__iexact=title_variant).first()


def build_full_hackathon_response(hackathon, request):
    from project.models import Project
    from project.serializers import ProjectSerializer

    teams = hackathon.teams.select_related('organizer').prefetch_related('members')
    individual_participants = hackathon.individual_participants.select_related(
        'user', 'team'
    ).prefetch_related('skills_offered')
    submissions = hackathon.submissions.select_related(
        'project', 'team'
    ).prefetch_related('reviews', 'reviews__judge')
    projects = Project.objects.filter(hackathon=hackathon).select_related('team')

    return {
        'hackathon': HackathonSerializer(hackathon, context={'request': request}).data,
        'teams': TeamSerializer(teams, many=True, context={'request': request}).data,
        'individual_participants': HackathonParticipantSerializer(individual_participants, many=True).data,
        'submissions': SubmissionSerializer(submissions, many=True).data,
        'projects': ProjectSerializer(projects, many=True).data,
    }


class HackathonCreateView(GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = CreateHackathonSerializer

    @swagger_auto_schema(
        request_body=CreateHackathonSerializer,
        responses={
            201: HackathonSerializer,
            400: "Bad Request",
            401: "Unauthorized",
            403: "Forbidden"
        },
        operation_description="Create a new hackathon (organizers with approved organizations only).",
        tags=['hackathons']
    )
    def post(self, request):
        user = request.user
        hackathon_title = request.data.get('title', 'Untitled Hackathon')

        # Check organizer permissions and explain the exact reason if not allowed
        if not user.is_organizer:
            user_orgs = user.organizations.all()
            if not user_orgs.exists():
                reason = "Your account does not have organizer privileges. You must first create an organization and have it approved by an admin before you can host a hackathon."
            elif all(not org.is_approved for org in user_orgs):
                org_names = ", ".join([f"'{org.name}'" for org in user_orgs])
                reason = f"Your organization ({org_names}) is currently pending admin approval. You will receive organizer access as soon as your organization is approved."
            else:
                reason = "Your account does not have organizer permissions enabled. Please contact an administrator."

            NotificationService.send_notification(
                user=user,
                title="Hackathon Creation Failed - Permission Required",
                message=reason,
                category='account',
                priority='high',
                send_email=True,
                send_in_app=True,
                template_name="emails/hackathon_creation_failed.html",
                context={
                    "user": user,
                    "hackathon_title": hackathon_title,
                    "reasons": [reason],
                    "action_url": "/organization",
                    "action_text": "Check Organization Status"
                }
            )
            return Response(
                {"detail": reason, "error": reason},
                status=status.HTTP_403_FORBIDDEN
            )

        serializer = self.serializer_class(data=request.data, context={'request': request})
        if not serializer.is_valid():
            reasons = []
            for field, errors in serializer.errors.items():
                if isinstance(errors, list):
                    for err in errors:
                        clean_err = str(err)
                        field_name = field.replace('_', ' ').capitalize()
                        reasons.append(f"{field_name}: {clean_err}" if field != 'non_field_errors' else clean_err)
                elif isinstance(errors, dict):
                    for subfield, suberrs in errors.items():
                        reasons.append(f"{subfield}: {suberrs}")
                else:
                    reasons.append(f"{field}: {errors}")

            NotificationService.send_notification(
                user=user,
                title="Hackathon Creation Failed",
                message="Your hackathon could not be created for the following reasons: " + "; ".join(reasons),
                category='account',
                priority='high',
                send_email=True,
                send_in_app=True,
                template_name="emails/hackathon_creation_failed.html",
                context={
                    "user": user,
                    "hackathon_title": hackathon_title,
                    "reasons": reasons,
                    "action_url": "/hackathons",
                    "action_text": "Review & Try Again"
                }
            )
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            hackathon = serializer.save()
        except Exception as e:
            error_reason = str(e)
            NotificationService.send_notification(
                user=user,
                title="Hackathon Creation Failed",
                message=f"An error occurred while saving your hackathon: {error_reason}",
                category='account',
                priority='high',
                send_email=True,
                send_in_app=True,
                template_name="emails/hackathon_creation_failed.html",
                context={
                    "user": user,
                    "hackathon_title": hackathon_title,
                    "reasons": [error_reason],
                    "action_url": "/hackathons",
                    "action_text": "Try Again"
                }
            )
            return Response(
                {"error": "Failed to create hackathon.", "detail": error_reason},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Send success notification to organizer
        NotificationService.send_notification(
            user=user,
            title="Hackathon Created Successfully",
            message=f"Your hackathon '{hackathon.title}' has been created successfully.",
            category='account',
            priority='normal',
            send_email=True,
            send_in_app=True,
            template_name="emails/CreatedHackathon.html",
            context={
                "user": user,
                "hackathon": hackathon,
                "hackathon_title": hackathon.title,
                "venue": hackathon.venue,
                "start_date": str(hackathon.start_date),
                "end_date": str(hackathon.end_date),
                "action_url": f"/hackathons/{hackathon.id}",
                "action_text": "View Hackathon"
            },
            data={
                'hackathon_id': hackathon.id,
                'hackathon_title': hackathon.title,
                'description': hackathon.description,
                'venue': hackathon.venue,
                'start_date': str(hackathon.start_date),
                'end_date': str(hackathon.end_date)
            }
        )
        return Response(
            {"message": "Hackathon created successfully.", "hackathon": HackathonSerializer(hackathon).data},
            status=status.HTTP_201_CREATED
        )


class HackathonPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'pageSize'
    page_query_param = 'page'
    max_page_size = 100


@method_decorator(cache_page(60 * 5), name='get')
class HackathonRetrieveByNameView(APIView):

    def get_permissions(self):
        return []

    @swagger_auto_schema(
        manual_parameters=[
            openapi.Parameter(
                'hackathon_name',
                openapi.IN_QUERY,
                description="Hackathon name or slug (e.g. global_hackathon)",
                type=openapi.TYPE_STRING,
                required=True,
            ),
        ],
        responses={
            200: "Full hackathon details with teams, participants, submissions, and projects",
            400: "Bad Request",
            404: "Hackathon not found",
        },
        operation_description="Retrieve a hackathon and all related data by name. No authentication required.",
        tags=['hackathons']
    )
    def get(self, request):
        hackathon_name = request.query_params.get('hackathon_name')
        if not hackathon_name or not hackathon_name.strip():
            return Response(
                {"error": "hackathon_name query parameter is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        hackathon = get_hackathon_by_name(hackathon_name)
        if not hackathon:
            return Response(
                {"error": "Hackathon not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response(build_full_hackathon_response(hackathon, request), status=status.HTTP_200_OK)


class HackathonStatsView(APIView):
    permission_classes = [AllowAny]

    @swagger_auto_schema(
        responses={
            200: openapi.Response(
                description="Public platform stats",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'active_participants': openapi.Schema(type=openapi.TYPE_INTEGER, description="Total active participants"),
                        'hackathons_hosted': openapi.Schema(type=openapi.TYPE_INTEGER, description="Total hackathons hosted"),
                        'organizations': openapi.Schema(type=openapi.TYPE_INTEGER, description="Total organizations"),
                    }
                )
            )
        },
        operation_description="Retrieve public platform statistics: active participants, hackathons hosted, and organizations.",
        tags=['hackathons']
    )
    def get(self, request):
        active_participants = User.objects.filter(
            Q(is_participant=True) | Q(hackathon_participations__isnull=False) | Q(teams__isnull=False),
            is_active=True
        ).distinct().count()
        hackathons_hosted = Hackathon.objects.count()
        organizations = Organization.objects.count()

        return Response({
            "active_participants": active_participants,
            "hackathons_hosted": hackathons_hosted,
            "organizations": organizations,
            "activeParticipants": active_participants,
            "hackathonsHosted": hackathons_hosted,
        }, status=status.HTTP_200_OK)


@method_decorator(cache_page(60 * 5), name='get')
class HackathonListView(ListCreateAPIView):
    serializer_class = HackathonSerializer

    def get_queryset(self):
        today = timezone.now().date()
        return Hackathon.objects.filter(
            visibility=True,
            end_date__gte=today
        ).select_related(
            'organization', 'organization__organizer'
        ).prefetch_related(
            'themes', 'skills', 'judges'
        ).order_by('-created_at')

    def get_permissions(self):
        if self.request.method == 'GET':
            return []
        return [IsAuthenticated()]

    @swagger_auto_schema(
        manual_parameters=[
            openapi.Parameter('page', openapi.IN_QUERY, description="Page number (default: 1)", type=openapi.TYPE_INTEGER),
            openapi.Parameter('pageSize', openapi.IN_QUERY, description="Items per page (default: 10, max: 100)", type=openapi.TYPE_INTEGER),
            openapi.Parameter('limit', openapi.IN_QUERY, description="Return N most recent active hackathons, bypasses page metadata", type=openapi.TYPE_INTEGER),
            openapi.Parameter('hackathon_name', openapi.IN_QUERY, description="Fetch a single hackathon and all related data by name (e.g. global_hackathon)", type=openapi.TYPE_STRING),
        ],
        responses={200: HackathonSerializer(many=True), 400: "Bad Request"},
        operation_description="List active public hackathons. Use page/pageSize for pagination or limit for a simple count. Pass hackathon_name to fetch a single hackathon with all related data. No authentication required.",
        tags=['hackathons']
    )
    def get(self, request, *args, **kwargs):
        # Route to the by-name handler whenever the param is present — even when
        # empty — so an empty value yields a 400 from that handler rather than
        # silently falling through to the list response.
        hackathon_name = request.query_params.get('hackathon_name')
        if hackathon_name is not None:
            return HackathonRetrieveByNameView().get(request)

        queryset = self.get_queryset()

        limit = request.query_params.get('limit')
        if limit is not None:
            try:
                limit = int(limit)
                if limit < 1:
                    raise ValueError
            except ValueError:
                return Response(
                    {"error": "limit must be a positive integer."},
                    status=status.HTTP_400_BAD_REQUEST
                )
            data = self.get_serializer(queryset[:limit], many=True).data
            return Response({"data": data, "limit": limit})

        paginator = HackathonPagination()
        try:
            page = paginator.paginate_queryset(queryset, request)
        except NotFound:
            total = queryset.count()
            page_size = paginator.get_page_size(request)
            return Response({
                "data": [],
                "pagination": {
                    "page": int(request.query_params.get(paginator.page_query_param, 1)),
                    "pageSize": page_size,
                    "totalItems": total,
                    "totalPages": math.ceil(total / page_size) if total else 1,
                }
            })

        serializer = self.get_serializer(page, many=True)
        return Response({
            "data": serializer.data,
            "pagination": {
                "page": paginator.page.number,
                "pageSize": paginator.get_page_size(request),
                "totalItems": paginator.page.paginator.count,
                "totalPages": paginator.page.paginator.num_pages,
            }
        })


@method_decorator(cache_page(60 * 5), name='get')
class HackathonRetrieveView(RetrieveUpdateDestroyAPIView):
    serializer_class = HackathonSerializer
    lookup_field = 'id'
    lookup_url_kwarg = 'hackathon_id'

    def get_queryset(self):
        return Hackathon.objects.all()

    def get_permissions(self):
        if self.request.method == 'GET':
            # Allow unauthenticated access for viewing hackathon details
            return []
        else:
            # Require authentication for updating/deleting hackathons
            return [IsAuthenticated()]

    @swagger_auto_schema(
        responses={
            200: HackathonSerializer,
            404: "Hackathon not found"
        },
        operation_description="Retrieve a hackathon's details. No authentication required.",
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
        # Send notification to organizer
        NotificationService.send_notification(
            user=request.user,
            title="Hackathon Deleted",
            message=f"Your hackathon '{hackathon.title}' has been deleted.",
            category='account',
            priority='normal',
            send_email=True,
            send_in_app=True,
            data={
                'hackathon_title': hackathon.title
            }
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
        
        # Send registration notification
        NotificationService.send_notification(
            user=request.user,
            title="Hackathon Registration Successful",
            message=f"You have been successfully registered for '{hackathon.title}'. You can now join existing teams or create a new team.",
            category='account',
            priority='normal',
            send_email=True,
            send_in_app=True,
            template_name="emails/JoinedHackethon.html",
            context={
                'user': request.user,
                'hackathon_title': hackathon.title,
                'start_date': str(hackathon.start_date),
                'end_date': str(hackathon.end_date),
                'action_url': f'/hackathons/{hackathon.id}',
                'action_text': 'View Hackathon'
            },
            data={
                'hackathon_id': hackathon.id,
                'hackathon_title': hackathon.title,
                'start_date': str(hackathon.start_date),
                'end_date': str(hackathon.end_date)
            },
            action_url=f'/hackathons/{hackathon.id}',
            action_text='View Hackathon'
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
    def post(self, request, hackathon_id):
        from project.models import Project

        # Get hackathon
        try:
            hackathon = Hackathon.objects.get(id=hackathon_id)
        except Hackathon.DoesNotExist:
            return Response({"error": "Hackathon does not exist."}, status=status.HTTP_404_NOT_FOUND)

        serializer = self.serializer_class(data=request.data, context={'request': request, 'hackathon_id': hackathon_id})
        serializer.is_valid(raise_exception=True)
        submission = serializer.save()

        # Send notification to team members
        for member in submission.team.members.all():
            NotificationService.send_notification(
                user=member,
                title="Project Submission Successful",
                message=f"Your project '{submission.project.title}' has been submitted to '{submission.hackathon.title}'.",
                category='account',
                priority='normal',
                send_email=True,
                send_in_app=True,
                template_name='emails/project_submission_successful.html',
                context={
                    'user': member,
                    'project_title': submission.project.title,
                    'hackathon_title': submission.hackathon.title,
                    'team_name': submission.team.name if submission.team else '',
                    'live_link': submission.project.live_link,
                    'github_url': submission.project.github_url,
                    'action_url': f'/submissions/{submission.id}',
                    'action_text': 'View Your Submission',
                },
                data={
                    'project_id': submission.project.id,
                    'project_title': submission.project.title,
                    'submission_id': submission.id,
                    'hackathon_id': submission.hackathon.id,
                    'hackathon_title': submission.hackathon.title
                },
                action_url=f'/submissions/{submission.id}',
                action_text='View Submission'
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
        
        # Base queryset with optimizations
        base_queryset = Submission.objects.select_related(
            'project', 'hackathon', 'hackathon__organization', 'team', 'team__organizer'
        ).prefetch_related(
            'team__members', 'reviews', 'reviews__judge'
        )
        
        # Optional filter by approved flag: ?approved=true or ?approved=false
        approved_filter = self.request.query_params.get('approved')
        if approved_filter is not None:
            if approved_filter.lower() in ['true', '1']:
                base_queryset = base_queryset.filter(approved=True)
            elif approved_filter.lower() in ['false', '0']:
                base_queryset = base_queryset.filter(approved=False)
        
        if not hackathon_id:
            return base_queryset.filter(team__members=self.request.user).order_by('-created_at')
            
        hackathon = Hackathon.objects.filter(id=hackathon_id).first()
        is_organizer = (
            (hackathon and hackathon.organization and (
                hackathon.organization.organizer == self.request.user or
                self.request.user in hackathon.organization.moderators.all()
            )) or self.request.user.is_admin
        )
        
        # Organizers, judges, or any request explicitly filtering approved=true can view all matching submissions
        if is_organizer or self.request.user.is_judge or approved_filter is not None:
            queryset = base_queryset.filter(hackathon_id=hackathon_id)
        else:
            queryset = base_queryset.filter(hackathon_id=hackathon_id, team__members=self.request.user)
        
        return queryset.order_by('-created_at')

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
        # Send notification to organizer for new submission
        submission = serializer.instance
        NotificationService.send_notification(
            user=hackathon.organization.organizer,
            title="New Submission Received",
            message=f"A new submission for '{hackathon.title}' has been received from team '{submission.team.name}'.",
            category='system',
            priority='normal',
            send_email=True,
            send_in_app=True,
            data={
                'hackathon_id': hackathon.id,
                'hackathon_title': hackathon.title,
                'submission_id': submission.id,
                'project_title': submission.project.title,
                'team_name': submission.team.name
            },
            action_url=f'/hackathons/{hackathon.id}/submissions',
            action_text='View Submissions'
        )

    def perform_update(self, serializer):
        submission = serializer.save()
        if submission.approved:
            # Send approval notification to team members
            for member in submission.team.members.all():
                NotificationService.send_notification(
                    user=member,
                    title="Submission Approved",
                    message=f"Your submission '{submission.project.title}' for '{submission.hackathon.title}' has been approved.",
                    category='account',
                    priority='high',
                    send_email=True,
                    send_in_app=True,
                    data={
                        'submission_id': submission.id,
                        'project_title': submission.project.title,
                        'hackathon_id': submission.hackathon.id,
                        'hackathon_title': submission.hackathon.title
                    },
                    action_url=f'/submissions/{submission.id}',
                    action_text='View Submission'
                )

    @action(detail=True, methods=['post'], url_path='approve')
    def approve(self, request, hackathon_id=None, pk=None):
        """Approve a submission (Organizer/Admin only)."""
        submission = self.get_object()
        hackathon = submission.hackathon

        # Verify permission
        is_organizer = (
            (hackathon.organization and (
                hackathon.organization.organizer == request.user or
                request.user in hackathon.organization.moderators.all()
            )) or request.user.is_admin
        )
        if not is_organizer:
            return Response(
                {"error": "Only the hackathon organizer or moderators can approve submissions."},
                status=status.HTTP_403_FORBIDDEN
            )

        submission.approved = True
        if submission.status == 'pending':
            submission.status = 'reviewed'
        submission.save()

        # Send approval notification to all team members
        for member in submission.team.members.all():
            NotificationService.send_notification(
                user=member,
                title="Submission Approved",
                message=f"Your submission '{submission.project.title}' for '{submission.hackathon.title}' has been approved.",
                category='account',
                priority='high',
                send_email=True,
                send_in_app=True,
                data={
                    'submission_id': submission.id,
                    'project_title': submission.project.title,
                    'hackathon_id': submission.hackathon.id,
                    'hackathon_title': submission.hackathon.title
                },
                action_url=f'/submissions/{submission.id}',
                action_text='View Submission'
            )

        return Response({
            "message": f"Submission for '{submission.project.title}' has been approved.",
            "submission": SubmissionSerializer(submission).data
        }, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], url_path='reject')
    def reject(self, request, hackathon_id=None, pk=None):
        """Reject a submission (Organizer/Admin only)."""
        submission = self.get_object()
        hackathon = submission.hackathon

        # Verify permission
        is_organizer = (
            (hackathon.organization and (
                hackathon.organization.organizer == request.user or
                request.user in hackathon.organization.moderators.all()
            )) or request.user.is_admin
        )
        if not is_organizer:
            return Response(
                {"error": "Only the hackathon organizer or moderators can reject submissions."},
                status=status.HTTP_403_FORBIDDEN
            )

        reason = request.data.get('reason', 'Submission does not meet requirements.')
        submission.approved = False
        submission.status = 'rejected'
        submission.save()

        # Send rejection notification to team members
        for member in submission.team.members.all():
            NotificationService.send_notification(
                user=member,
                title="Submission Update",
                message=f"Your submission '{submission.project.title}' for '{submission.hackathon.title}' was rejected. Reason: {reason}",
                category='account',
                priority='normal',
                send_email=True,
                send_in_app=True,
                data={
                    'submission_id': submission.id,
                    'project_title': submission.project.title,
                    'hackathon_id': submission.hackathon.id,
                    'reason': reason
                },
                action_url=f'/submissions/{submission.id}',
                action_text='View Submission'
            )

        return Response({
            "message": f"Submission for '{submission.project.title}' has been rejected.",
            "submission": SubmissionSerializer(submission).data
        }, status=status.HTTP_200_OK)


class ReviewViewSet(ModelViewSet):
    serializer_class = ReviewSerializer

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAuthenticated(), IsJudge()]
        return [IsAuthenticated()]

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return Review.objects.none()
        hackathon_id = self.kwargs.get('hackathon_id')
        
        # Base queryset with optimizations
        base_queryset = Review.objects.select_related(
            'submission', 'submission__project', 'submission__hackathon',
            'submission__hackathon__organization', 'submission__team', 'judge'
        )
        
        if not hackathon_id:
            return base_queryset.filter(judge=self.request.user).order_by('-created_at')
            
        hackathon = Hackathon.objects.filter(id=hackathon_id).first()
        is_organizer = (
            (hackathon and hackathon.organization and (
                hackathon.organization.organizer == self.request.user or
                self.request.user in hackathon.organization.moderators.all()
            )) or self.request.user.is_admin
        )
        
        if is_organizer or self.request.user.is_judge:
            # Organizers and judges can view all reviews for this hackathon
            return base_queryset.filter(submission__hackathon_id=hackathon_id).order_by('-created_at')
        else:
            # Participants can view reviews for their own team's submissions
            return base_queryset.filter(
                submission__hackathon_id=hackathon_id,
                submission__team__members=self.request.user
            ).order_by('-created_at')

    def perform_create(self, serializer):
        serializer.save(judge=self.request.user)
        # Update submission status to reviewed only when ALL judges have reviewed
        review = serializer.instance
        submission = review.submission
        hackathon = submission.hackathon
        
        # Get all judges assigned to this hackathon
        all_judges = set(hackathon.judges.values_list('id', flat=True))
        
        # Get all judges who have reviewed this submission
        reviewed_judges = set(Review.objects.filter(submission=submission).values_list('judge_id', flat=True))
        
        # Only mark as 'reviewed' if all judges have completed their reviews
        if submission.status == 'pending' and all_judges and reviewed_judges == all_judges:
            submission.status = 'reviewed'
            submission.save()
        
        # Send review notification to submission team
        for member in review.submission.team.members.all():
            NotificationService.send_notification(
                user=member,
                title="New Review for Your Submission",
                message=f"Your submission '{review.submission.project.title}' for '{review.submission.hackathon.title}' has received a new review.",
                category='account',
                priority='normal',
                send_email=True,
                send_in_app=True,
                template_name='emails/submission_review.html',
                context={
                    'user': member,
                    'project_title': review.submission.project.title,
                    'hackathon_title': review.submission.hackathon.title,
                    'overall_score': review.overall_score,
                    'review_comments': review.review or 'No comments provided',
                    'action_url': f'/submissions/{review.submission.id}',
                    'action_text': 'View Full Review & Scores',
                },
                data={
                    'review_id': review.id,
                    'submission_id': review.submission.id,
                    'project_title': review.submission.project.title,
                    'hackathon_title': review.submission.hackathon.title,
                    'overall_score': review.overall_score,
                    'review_comments': review.review or 'No comments provided'
                },
                action_url=f'/submissions/{review.submission.id}',
                action_text='View Review'
            )

    def perform_update(self, serializer):
        serializer.save()
        # Update submission status to reviewed only when ALL judges have reviewed
        review = serializer.instance
        submission = review.submission
        hackathon = submission.hackathon
        
        # Get all judges assigned to this hackathon
        all_judges = set(hackathon.judges.values_list('id', flat=True))
        
        # Get all judges who have reviewed this submission
        reviewed_judges = set(Review.objects.filter(submission=submission).values_list('judge_id', flat=True))
        
        # Only mark as 'reviewed' if all judges have completed their reviews
        if submission.status == 'pending' and all_judges and reviewed_judges == all_judges:
            submission.status = 'reviewed'
            submission.save()


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
        reviews = Review.objects.filter(
            judge=request.user
        ).select_related(
            'submission__hackathon', 'submission__hackathon__organization',
            'submission__project', 'submission__team', 'submission__team__organizer'
        ).prefetch_related(
            'submission__team__members'
        ).order_by('-created_at')
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
            200: UserSerializer.PublicSerializer(many=True),
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
        serializer = UserSerializer.PublicSerializer(judges, many=True)
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
        # Get all organizations where the user is the organizer
        user_orgs = request.user.organizations.all()
        if not user_orgs.exists():
            return Response({"error": "You don't have an organization."}, status=status.HTTP_400_BAD_REQUEST)

        # Get all hackathons from user's organizations with optimizations
        hackathons = Hackathon.objects.filter(
            organization__in=user_orgs
        ).select_related(
            'organization', 'organization__organizer'
        ).prefetch_related(
            'themes', 'skills', 'judges'
        ).order_by('-created_at')
        serializer = HackathonSerializer(hackathons, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


@method_decorator(cache_page(60 * 5), name='get')
class OrganizationHackathonsView(APIView):

    def get_permissions(self):
        return []

    @swagger_auto_schema(
        responses={
            200: HackathonSerializer(many=True),
            404: "Organization not found"
        },
        operation_description="Fetch all hackathons for a specific organization. No authentication required.",
        tags=['hackathons']
    )
    def get(self, request, organization_id):
        from organization.models import Organization
        try:
            organization = Organization.objects.get(id=organization_id)
        except Organization.DoesNotExist:
            return Response({"error": "Organization not found."}, status=status.HTTP_404_NOT_FOUND)

        # Get all hackathons for this organization with optimizations
        hackathons = Hackathon.objects.filter(
            organization=organization
        ).select_related(
            'organization', 'organization__organizer'
        ).prefetch_related(
            'themes', 'skills', 'judges'
        ).order_by('-created_at')
        serializer = HackathonSerializer(hackathons, many=True)
        return Response({
            "organization": {
                "id": organization.id,
                "name": organization.name
            },
            "hackathons_count": hackathons.count(),
            "hackathons": serializer.data
        }, status=status.HTTP_200_OK)




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
        
        # Send notification to user about joining team
        NotificationService.send_notification(
            user=request.user,
            title=f"Joined Team for {hackathon.title}",
            message=f"You have successfully joined team '{team.name}' for '{hackathon.title}'.",
            category='account',
            priority='normal',
            send_email=True,
            send_in_app=True,
            template_name="emails/Joinedteam.html",
            context={
                'user': request.user,
                'team_name': team.name,
                'hackathon_title': hackathon.title,
                'action_url': f'/teams/{team.id}',
                'action_text': 'View Team'
            },
            data={
                'team_id': team.id,
                'team_name': team.name,
                'hackathon_id': hackathon.id,
                'hackathon_title': hackathon.title
            },
            action_url=f'/teams/{team.id}',
            action_text='View Team'
        )

        # Notify existing team members
        other_members = team.members.exclude(id=request.user.id)
        for member in other_members:
            NotificationService.send_notification(
                user=member,
                title=f"New Team Member Joined - {hackathon.title}",
                message=f"{request.user.get_full_name() or request.user.username} has joined your team '{team.name}' for '{hackathon.title}'.",
                category='account',
                priority='normal',
                send_email=True,
                send_in_app=True,
                data={
                    'new_member_name': request.user.get_full_name() or request.user.username,
                    'team_id': team.id,
                    'team_name': team.name,
                    'hackathon_id': hackathon.id,
                    'hackathon_title': hackathon.title
                },
                action_url=f'/teams/{team.id}',
                action_text='View Team'
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


class HackathonProjectsView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        responses={
            200: "List of all projects in the hackathon",
            401: "Unauthorized",
            403: "Forbidden - Only organizers, judges, and admins can view all projects",
            404: "Hackathon not found"
        },
        operation_description="Get all projects in a specific hackathon. Only accessible by organizers, judges, and admins.",
        tags=['projects']
    )
    def get(self, request, hackathon_id):
        try:
            hackathon = Hackathon.objects.get(id=hackathon_id)
        except Hackathon.DoesNotExist:
            return Response({"error": "Hackathon not found."}, status=status.HTTP_404_NOT_FOUND)

        # Check if user has permission to view all projects
        is_organizer = (hackathon.organization and
                       (hackathon.organization.organizer == request.user or
                        request.user in hackathon.organization.moderators.all()))
        is_judge = request.user in hackathon.judges.all()
        is_admin = request.user.is_admin

        if not (is_organizer or is_judge or is_admin):
            return Response(
                {"error": "You do not have permission to view all projects in this hackathon. Only organizers, judges, and admins can access this endpoint."},
                status=status.HTTP_403_FORBIDDEN
            )

        # Get all projects for this hackathon
        from project.models import Project
        from project.serializers import ProjectSerializer

        projects = Project.objects.filter(hackathon=hackathon).select_related('team', 'hackathon')
        serializer = ProjectSerializer(projects, many=True)

        return Response({
            "hackathon": {
                "id": hackathon.id,
                "title": hackathon.title
            },
            "projects_count": projects.count(),
            "projects": serializer.data
        }, status=status.HTTP_200_OK)


class SubmissionProjectDetailView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        responses={
            200: "Project details retrieved successfully",
            404: "Submission not found",
            403: "Forbidden"
        },
        operation_description="Get project details using submission ID.",
        tags=['hackathons']
    )
    def get(self, request, submission_id):
        """
        Get project details from a submission ID.
        Accessible by submission team members, judges, and organizers.
        """
        try:
            submission = Submission.objects.get(id=submission_id)
        except Submission.DoesNotExist:
            return Response(
                {"error": "Submission not found."},
                status=status.HTTP_404_NOT_FOUND
            )

        # Check permissions - allow team members, judges, organizers, and admins
        user = request.user
        has_access = (
            user in submission.team.members.all() or  # Team member
            user.is_judge or  # Judge
            user.is_organizer or  # Organizer
            user.is_admin  # Admin
        )

        if not has_access:
            return Response(
                {"error": "You don't have permission to view this project."},
                status=status.HTTP_403_FORBIDDEN
            )

        # Import ProjectSerializer
        from project.serializers import ProjectSerializer

        project = submission.project
        serializer = ProjectSerializer(project)

        return Response({
            "submission": {
                "id": submission.id,
                "status": submission.status,
                "approved": submission.approved,
                "created_at": submission.created_at,
                "updated_at": submission.updated_at
            },
            "project": serializer.data
        }, status=status.HTTP_200_OK)


class HackathonLeaderboardView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        responses={
            200: "Leaderboard retrieved successfully",
            404: "Hackathon not found"
        },
        operation_description="Get the ranked leaderboard for a hackathon based on judge evaluations and scores.",
        tags=['hackathons']
    )
    def get(self, request, hackathon_id):
        try:
            hackathon = Hackathon.objects.get(id=hackathon_id)
        except Hackathon.DoesNotExist:
            return Response({"error": "Hackathon not found."}, status=status.HTTP_404_NOT_FOUND)

        is_organizer = (
            (hackathon.organization and (
                hackathon.organization.organizer == request.user or
                request.user in hackathon.organization.moderators.all()
            )) or request.user.is_admin
        )

        # Check if results have been released by the organizer
        if not hackathon.results_released and not is_organizer:
            return Response({
                "hackathon": {
                    "id": hackathon.id,
                    "title": hackathon.title
                },
                "results_released": False,
                "message": "Results for this hackathon have not been released by the organizer yet. Stay tuned!",
                "total_submissions": 0,
                "leaderboard": []
            }, status=status.HTTP_200_OK)

        # Optional filter: ?approved_only=true
        approved_only = request.query_params.get('approved_only', 'false').lower() in ['true', '1']

        submissions_qs = Submission.objects.filter(hackathon=hackathon).select_related(
            'project', 'team', 'team__organizer'
        ).prefetch_related(
            'reviews', 'reviews__judge'
        )

        if approved_only:
            submissions_qs = submissions_qs.filter(approved=True)

        leaderboard_data = []

        for sub in submissions_qs:
            reviews = list(sub.reviews.all())
            reviews_count = len(reviews)

            if reviews_count > 0:
                avg_overall = round(sum(r.overall_score for r in reviews) / reviews_count, 2)
                avg_innovation = round(sum(r.innovation_score for r in reviews) / reviews_count, 2)
                avg_technical = round(sum(r.technical_score for r in reviews) / reviews_count, 2)
                avg_ux = round(sum(r.user_experience_score for r in reviews) / reviews_count, 2)
                avg_impact = round(sum(r.impact_score for r in reviews) / reviews_count, 2)
                avg_presentation = round(sum(r.presentation_score for r in reviews) / reviews_count, 2)
            else:
                avg_overall = 0.0
                avg_innovation = 0.0
                avg_technical = 0.0
                avg_ux = 0.0
                avg_impact = 0.0
                avg_presentation = 0.0

            leaderboard_data.append({
                'submission_id': sub.id,
                'project': {
                    'id': sub.project.id,
                    'title': sub.project.title,
                    'description': sub.project.description,
                    'github_url': sub.project.github_url,
                    'demo_video_url': sub.project.demo_video_url,
                    'live_link': sub.project.live_link,
                    'presentation_link': sub.project.presentation_link,
                },
                'team': {
                    'id': sub.team.id,
                    'name': sub.team.name,
                },
                'approved': sub.approved,
                'status': sub.status,
                'scores': {
                    'average_overall_score': avg_overall,
                    'average_innovation_score': avg_innovation,
                    'average_technical_score': avg_technical,
                    'average_user_experience_score': avg_ux,
                    'average_impact_score': avg_impact,
                    'average_presentation_score': avg_presentation,
                    'reviews_count': reviews_count,
                },
                'reviews': [
                    {
                        'id': r.id,
                        'judge': {
                            'id': r.judge.id,
                            'username': r.judge.username,
                            'first_name': r.judge.first_name,
                            'last_name': r.judge.last_name,
                        },
                        'overall_score': r.overall_score,
                        'innovation_score': r.innovation_score,
                        'technical_score': r.technical_score,
                        'user_experience_score': r.user_experience_score,
                        'impact_score': r.impact_score,
                        'presentation_score': r.presentation_score,
                        'review': r.review,
                        'created_at': r.created_at
                    }
                    for r in reviews
                ]
            })

        # Sort descending by average overall score, then by reviews count
        leaderboard_data.sort(
            key=lambda item: (item['scores']['average_overall_score'], item['scores']['reviews_count']),
            reverse=True
        )

        # Assign ranks
        for idx, item in enumerate(leaderboard_data, 1):
            item['rank'] = idx

        response_data = {
            "hackathon": {
                "id": hackathon.id,
                "title": hackathon.title
            },
            "results_released": hackathon.results_released,
            "results_released_at": hackathon.results_released_at,
            "is_organizer_preview": (not hackathon.results_released and is_organizer),
            "total_submissions": len(leaderboard_data),
            "leaderboard": leaderboard_data
        }

        if not hackathon.results_released and is_organizer:
            response_data["organizer_notice"] = (
                "These results are currently in preview mode and NOT released to participants. "
                "Use POST /release-results/ to officially release them."
            )

        return Response(response_data, status=status.HTTP_200_OK)


class HackathonLiveReviewsView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        responses={
            200: "Live reviews retrieved successfully",
            404: "Hackathon not found"
        },
        operation_description="Get live feed of all judge reviews submitted for a hackathon.",
        tags=['hackathons']
    )
    def get(self, request, hackathon_id):
        try:
            hackathon = Hackathon.objects.get(id=hackathon_id)
        except Hackathon.DoesNotExist:
            return Response({"error": "Hackathon not found."}, status=status.HTTP_404_NOT_FOUND)

        is_organizer = (
            (hackathon.organization and (
                hackathon.organization.organizer == request.user or
                request.user in hackathon.organization.moderators.all()
            )) or request.user.is_admin
        )
        is_judge = request.user in hackathon.judges.all()

        reviews = Review.objects.filter(
            submission__hackathon=hackathon
        ).select_related(
            'submission', 'submission__project', 'submission__team', 'judge'
        ).order_by('-created_at')

        # If results have not been released, non-organizers and non-judges only see their own team's reviews
        if not hackathon.results_released and not (is_organizer or is_judge):
            reviews = reviews.filter(submission__team__members=request.user)

        data = [
            {
                'id': r.id,
                'submission_id': r.submission.id,
                'project': {
                    'id': r.submission.project.id,
                    'title': r.submission.project.title,
                    'github_url': r.submission.project.github_url,
                    'live_link': r.submission.project.live_link,
                },
                'team': {
                    'id': r.submission.team.id,
                    'name': r.submission.team.name,
                },
                'judge': {
                    'id': r.judge.id,
                    'username': r.judge.username,
                    'first_name': r.judge.first_name,
                    'last_name': r.judge.last_name,
                },
                'overall_score': r.overall_score,
                'innovation_score': r.innovation_score,
                'technical_score': r.technical_score,
                'user_experience_score': r.user_experience_score,
                'impact_score': r.impact_score,
                'presentation_score': r.presentation_score,
                'review': r.review,
                'created_at': r.created_at,
            }
            for r in reviews
        ]

        return Response({
            "hackathon": {
                "id": hackathon.id,
                "title": hackathon.title
            },
            "results_released": hackathon.results_released,
            "total_reviews": len(data),
            "reviews": data
        }, status=status.HTTP_200_OK)


class HackathonApprovedSubmissionsView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        responses={
            200: "Approved submissions retrieved successfully",
            404: "Hackathon not found"
        },
        operation_description="Get all approved project submissions for a hackathon.",
        tags=['hackathons']
    )
    def get(self, request, hackathon_id):
        try:
            hackathon = Hackathon.objects.get(id=hackathon_id)
        except Hackathon.DoesNotExist:
            return Response({"error": "Hackathon not found."}, status=status.HTTP_404_NOT_FOUND)

        submissions = Submission.objects.filter(
            hackathon=hackathon, approved=True
        ).select_related(
            'project', 'team', 'hackathon'
        ).prefetch_related(
            'reviews', 'reviews__judge'
        ).order_by('-created_at')

        serializer = SubmissionSerializer(submissions, many=True)
        return Response({
            "hackathon": {
                "id": hackathon.id,
                "title": hackathon.title
            },
            "count": submissions.count(),
            "submissions": serializer.data
        }, status=status.HTTP_200_OK)


class HackathonReleaseResultsView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'release': openapi.Schema(type=openapi.TYPE_BOOLEAN, description='True to release/publish results, False to withdraw/hide', default=True),
            }
        ),
        responses={
            200: "Results release status updated successfully",
            403: "Only hackathon organizer can release results",
            404: "Hackathon not found"
        },
        operation_description="Organizer endpoint to release or hide the official hackathon results and leaderboard.",
        tags=['hackathons']
    )
    def post(self, request, hackathon_id):
        try:
            hackathon = Hackathon.objects.get(id=hackathon_id)
        except Hackathon.DoesNotExist:
            return Response({"error": "Hackathon not found."}, status=status.HTTP_404_NOT_FOUND)

        is_organizer = (
            (hackathon.organization and (
                hackathon.organization.organizer == request.user or
                request.user in hackathon.organization.moderators.all()
            )) or request.user.is_admin
        )
        if not is_organizer:
            return Response(
                {"error": "Only the hackathon organizer or moderators can release results."},
                status=status.HTTP_403_FORBIDDEN
            )

        release = request.data.get('release', True)
        if isinstance(release, str):
            release = release.lower() in ['true', '1']

        hackathon.results_released = bool(release)
        if hackathon.results_released:
            hackathon.results_released_at = timezone.now()
        hackathon.save()

        # If results released, notify participants
        if hackathon.results_released:
            try:
                from accounts.models import User
                from django.db.models import Q
                participants = User.objects.filter(
                    Q(hackathon_participations__hackathon=hackathon) |
                    Q(teams__hackathon=hackathon)
                ).distinct()

                for participant in participants:
                    NotificationService.send_notification(
                        recipient=participant,
                        title=f"Results Released: {hackathon.title}",
                        message=f"The organizer has officially released the results and leaderboard for '{hackathon.title}'. Check out the winners and final scores!",
                        notification_type="HACKATHON_RESULTS",
                        extra_data={
                            "hackathon_id": hackathon.id,
                            "hackathon_title": hackathon.title,
                            "url": f"/dashboard/{hackathon.id}/leaderboard"
                        }
                    )
            except Exception as e:
                logger.error(f"Error sending results release notifications: {e}")

        status_text = "released" if hackathon.results_released else "withdrawn"
        return Response({
            "message": f"Hackathon results have been successfully {status_text}.",
            "hackathon": {
                "id": hackathon.id,
                "title": hackathon.title
            },
            "results_released": hackathon.results_released,
            "results_released_at": hackathon.results_released_at,
        }, status=status.HTTP_200_OK)

    def get(self, request, hackathon_id):
        try:
            hackathon = Hackathon.objects.get(id=hackathon_id)
        except Hackathon.DoesNotExist:
            return Response({"error": "Hackathon not found."}, status=status.HTTP_404_NOT_FOUND)

        is_organizer = (
            (hackathon.organization and (
                hackathon.organization.organizer == request.user or
                request.user in hackathon.organization.moderators.all()
            )) or request.user.is_admin
        )

        return Response({
            "hackathon_id": hackathon.id,
            "title": hackathon.title,
            "results_released": hackathon.results_released,
            "results_released_at": hackathon.results_released_at,
            "can_release": is_organizer
        }, status=status.HTTP_200_OK)




