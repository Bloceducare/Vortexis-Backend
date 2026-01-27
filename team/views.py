from rest_framework import status
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import PermissionDenied
from rest_framework.generics import GenericAPIView
from django.core.mail import send_mail
from django.conf import settings
from notifications.services import NotificationService
from .serializers import CreateTeamSerializer, TeamSerializer, UpdateTeamSerializer, AddMemberSerializer, RemoveMemberSerializer, LeaveTeamSerializer, AcceptTeamInvitationSerializer, TeamInvitationSerializer, TeamJoinRequestSerializer
from .models import Team
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from .models import Team, TeamJoinRequest
from django.shortcuts import get_object_or_404

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
        team = serializer.save()
        
        # Send email notifications to all team members
        send_mail(
            subject=f"Team Created for {team.hackathon.title}",
            message=f"Dear Team,\n\nA new team '{team.name}' has been created for '{team.hackathon.title}'.\nTeam Organizer: {((team.organizer.first_name + ' ' + team.organizer.last_name).strip() or team.organizer.username) if team.organizer else 'Unknown'}\nMembers: {', '.join([((member.first_name + ' ' + member.last_name).strip() or member.username) for member in team.members.all()])}\n\nGood luck with the hackathon!",
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[member.email for member in team.members.all()],
            fail_silently=True
        )
    
    def perform_destroy(self, instance):
        if instance.organizer != self.request.user:
            raise PermissionDenied("You are not authorized to delete this team.")
        
        # Update participant records before deleting team
        from hackathon.models import HackathonParticipant
        for member in instance.members.all():
            try:
                participant = HackathonParticipant.objects.get(
                    hackathon=instance.hackathon, 
                    user=member
                )
                participant.team = None
                participant.looking_for_team = True
                participant.save()
            except HackathonParticipant.DoesNotExist:
                pass
        
        instance.delete()
    
    @swagger_auto_schema(
        request_body=AddMemberSerializer,
        responses={
            200: TeamSerializer,
            400: "Bad Request - validation errors",
            403: "Forbidden - not the team organizer", 
            404: "Team not found"
        },
        operation_description="Add a member to the team by email. Only team organizers can add members.",
        tags=['teams']
    )
    @action(detail=True, methods=['post'], serializer_class=AddMemberSerializer)
    def add_member(self, request, pk=None):
        """Send invitation to join the team"""
        team = self.get_object()
        serializer = AddMemberSerializer(team, data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        result = serializer.save()
        return Response({
            'message': result['message'],
            'user_exists': result['user_exists'],
            'invitation_id': result['invitation'].id
        }, status=status.HTTP_200_OK)
    
    @swagger_auto_schema(
        request_body=RemoveMemberSerializer,
        responses={
            200: TeamSerializer,
            400: "Bad Request - validation errors",
            403: "Forbidden - not the team organizer",
            404: "Team not found"
        },
        operation_description="Remove a member from the team by email. Only team organizers can remove members.",
        tags=['teams']
    )
    @action(detail=True, methods=['post'], serializer_class=RemoveMemberSerializer)
    def remove_member(self, request, pk=None):
        """Remove a member from the team"""
        team = self.get_object()
        serializer = RemoveMemberSerializer(team, data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({'team': TeamSerializer(team).data}, status=status.HTTP_200_OK)
    
    @swagger_auto_schema(
        request_body=LeaveTeamSerializer,
        responses={
            200: "Successfully left the team",
            400: "Bad Request - validation errors",
            403: "Forbidden - not a team member or trying to leave as organizer",
            404: "Team not found"
        },
        operation_description="Leave a team. Team organizers cannot leave their own team.",
        tags=['teams']
    )
    @action(detail=True, methods=['post'], serializer_class=LeaveTeamSerializer)
    def leave_team(self, request, pk=None):
        """Leave a team"""
        team = self.get_object()
        serializer = LeaveTeamSerializer(team, data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        
        # Send notification email to team organizer and remaining members
        remaining_members = team.members.all()
        if remaining_members.exists():
            recipient_emails = [member.email for member in remaining_members]
            send_mail(
                subject=f"Member Left Team: {team.name}",
                message=f"Dear Team,\n\n{(request.user.first_name + ' ' + request.user.last_name).strip() or request.user.username} has left the team '{team.name}'.\n\nRemaining members: {', '.join([((member.first_name + ' ' + member.last_name).strip() or member.username) for member in remaining_members])}\n\nTeam Organizer: {((team.organizer.first_name + ' ' + team.organizer.last_name).strip() or team.organizer.username) if team.organizer else 'Unknown'}",
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=recipient_emails,
                fail_silently=True
            )
        
        return Response(
            {'message': f'You have successfully left the team "{team.name}".'},
            status=status.HTTP_200_OK
        )
    
    @swagger_auto_schema(
        responses={
            200: TeamSerializer(many=True),
        },
        operation_description="Get all teams that the authenticated user is part of, regardless of hackathons",
        tags=['teams']
    )
    @action(detail=False, methods=['get'])
    def my_teams(self, request):
        """Get all teams the authenticated user is part of, regardless of hackathons"""
        # Get all teams where user is a member or organizer
        teams = Team.objects.filter(members=request.user).distinct().order_by('-created_at')
        serializer = TeamSerializer(teams, many=True, context={'request': request})
        return Response({
            'count': teams.count(),
            'teams': serializer.data
        }, status=status.HTTP_200_OK)
    
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
        
        try:
            hackathon_id = int(hackathon_id)
        except ValueError:
            return Response({'error': 'Invalid hackathon_id'}, status=status.HTTP_400_BAD_REQUEST)
        
        team = Team.objects.filter(
            members=request.user, 
            hackathon_id=hackathon_id
        ).first()
        
        if team:
            return Response(TeamSerializer(team).data, status=status.HTTP_200_OK)
        return Response({'message': 'No team found for this hackathon'}, status=status.HTTP_404_NOT_FOUND)
    
    @swagger_auto_schema(
        request_body=AcceptTeamInvitationSerializer,
        responses={
            200: "Successfully joined team",
            400: "Bad Request - invalid or expired token",
            404: "Invitation not found"
        },
        operation_description="Accept a team invitation using the invitation token",
        tags=['teams']
    )
    @action(detail=False, methods=['post'])
    def accept_invitation(self, request):
        """Accept a team invitation"""
        serializer = AcceptTeamInvitationSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        result = serializer.save()
        return Response({
            'message': result['message'],
            'team': TeamSerializer(result['team']).data
        }, status=status.HTTP_200_OK)

    @swagger_auto_schema(
        responses={
            200: TeamSerializer,
            404: "Team not found"
        },
        operation_description="Get team details by team ID",
        tags=['teams']
    )
    @action(detail=True, methods=['get'])
    def details(self, request, pk=None):
        """Get team details by ID"""
        try:
            team = Team.objects.get(pk=pk)
            return Response(TeamSerializer(team).data, status=status.HTTP_200_OK)
        except Team.DoesNotExist:
            return Response({'error': 'Team not found'}, status=status.HTTP_404_NOT_FOUND)

    @swagger_auto_schema(
        manual_parameters=[
            openapi.Parameter(
                'team_id',
                openapi.IN_QUERY,
                description='Filter join requests by team ID (optional)',
                type=openapi.TYPE_INTEGER,
                required=False
            ),
            openapi.Parameter(
                'status',
                openapi.IN_QUERY,
                description='Filter by status: pending, approved, or rejected (optional)',
                type=openapi.TYPE_STRING,
                required=False,
                enum=['pending', 'approved', 'rejected']
            ),
        ],
        responses={
            200: TeamJoinRequestSerializer(many=True),
        },
        operation_description="Get all join requests. Returns requests for teams the user organizes, or requests made by the user. Can filter by team_id and status.",
        tags=['teams']
    )
    @action(detail=False, methods=['get'])
    def join_requests(self, request):
        """Get all join requests - for teams user organizes or requests made by user"""
        team_id = request.query_params.get('team_id')
        status_filter = request.query_params.get('status')
        
        # Get teams where user is organizer
        organized_teams = Team.objects.filter(organizer=request.user)
        
        # Get join requests for teams user organizes
        join_requests = TeamJoinRequest.objects.filter(team__in=organized_teams)
        
        # Also include requests made by the user
        user_requests = TeamJoinRequest.objects.filter(user=request.user)
        
        # Combine and get distinct
        all_requests = (join_requests | user_requests).distinct()
        
        # Apply filters
        if team_id:
            try:
                all_requests = all_requests.filter(team_id=int(team_id))
            except ValueError:
                return Response({'error': 'Invalid team_id'}, status=status.HTTP_400_BAD_REQUEST)
        
        if status_filter:
            if status_filter not in ['pending', 'approved', 'rejected']:
                return Response({'error': 'Invalid status. Must be: pending, approved, or rejected'}, status=status.HTTP_400_BAD_REQUEST)
            all_requests = all_requests.filter(status=status_filter)
        
        # Order by created_at (newest first)
        all_requests = all_requests.order_by('-created_at')
        
        serializer = TeamJoinRequestSerializer(all_requests, many=True)
        return Response({
            'count': all_requests.count(),
            'join_requests': serializer.data
        }, status=status.HTTP_200_OK)

    @swagger_auto_schema(
        manual_parameters=[
            openapi.Parameter(
                'team_id',
                openapi.IN_QUERY,
                description='The ID of the team to get join requests for',
                type=openapi.TYPE_INTEGER,
                required=True
            ),
        ],
        responses={
            200: TeamJoinRequestSerializer(many=True),
            400: "Bad Request - team_id parameter required",
            403: "Forbidden - not team organizer",
            404: "Team not found"
        },
        operation_description="Get all join requests for a specific team. Only team organizer can view requests.",
        tags=['teams']
    )
    @action(detail=False, methods=['get'])
    def team_join_requests(self, request):
        """Get all join requests for a specific team"""
        team_id = request.query_params.get('team_id')
        if not team_id:
            return Response({'error': 'team_id parameter is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            team_id = int(team_id)
        except ValueError:
            return Response({'error': 'Invalid team_id'}, status=status.HTTP_400_BAD_REQUEST)
        
        team = get_object_or_404(Team, id=team_id)
        
        # Check if user is organizer
        if team.organizer != request.user:
            return Response({'error': 'Only the team organizer can view join requests'}, status=status.HTTP_403_FORBIDDEN)
        
        join_requests = TeamJoinRequest.objects.filter(team=team).order_by('-created_at')
        serializer = TeamJoinRequestSerializer(join_requests, many=True)
        
        return Response({
            'team': {
                'id': team.id,
                'name': team.name,
                'hackathon': team.hackathon.title
            },
            'count': join_requests.count(),
            'join_requests': serializer.data
        }, status=status.HTTP_200_OK)

    @swagger_auto_schema(
        responses={
            200: TeamJoinRequestSerializer(many=True),
        },
        operation_description="Get all join requests made by the authenticated user",
        tags=['teams']
    )
    @action(detail=False, methods=['get'])
    def my_join_requests(self, request):
        """Get all join requests made by the authenticated user"""
        join_requests = TeamJoinRequest.objects.filter(user=request.user).order_by('-created_at')
        serializer = TeamJoinRequestSerializer(join_requests, many=True)
        
        return Response({
            'count': join_requests.count(),
            'join_requests': serializer.data
        }, status=status.HTTP_200_OK)

    @swagger_auto_schema(
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'team_id': openapi.Schema(type=openapi.TYPE_INTEGER, description='ID of the team to join'),
            },
            required=['team_id']
        ),
        responses={
            201: "Join request sent successfully",
            400: "Bad Request - validation errors",
            404: "Team not found"
        },
        operation_description="Request to join a team",
        tags=['teams']
    )
    @action(detail=False, methods=['post'])
    def request_to_join(self, request):
        if not request.user.is_authenticated:
            return Response({'error': 'Authentication required.'}, status=401)

        team_id = request.data.get('team_id')
        if not team_id:
            return Response({'error': 'team_id is required'}, status=400)

        team = get_object_or_404(Team, id=team_id)
        user = request.user

        if team.members.filter(id=user.id).exists():
            return Response({'error': 'You are already a member of this team'}, status=400)

        already_in_team = Team.objects.filter(hackathon=team.hackathon, members=user).exists()
        if already_in_team:
            return Response({'error': 'You are already in a team for this hackathon'}, status=400)

        join_request, created = TeamJoinRequest.objects.get_or_create(team=team, user=user, defaults={'status': 'pending'})

        if not created:
            if join_request.status == 'pending':
                return Response({'error': 'Join request already sent and is pending'}, status=400)
            elif join_request.status == 'approved':
                return Response({'error': 'Your join request was already approved'}, status=400)
            elif join_request.status == 'rejected':
                # Allow resubmission if previously rejected
                join_request.status = 'pending'
                join_request.save()
            else:
                return Response({'error': 'Join request already exists'}, status=400)

        # Notify team organizer and members
        user_name = (user.first_name + ' ' + user.last_name).strip() or user.username
        subject = f"New Join Request for Team: {team.name}"
        message = f"Dear Team,\n\n{user_name} ({user.email}) has requested to join your team '{team.name}' for '{team.hackathon.title}'.\n\nPlease review and respond to the request."
        
        # Notify organizer
        if team.organizer:
            NotificationService.send_notification(
                user=team.organizer,
                title=subject,
                message=message,
                category='team',
                priority='normal',
                send_email=True,
                send_in_app=True,
                data={'team_id': team.id, 'join_request_id': join_request.id, 'action': 'join_request_received'}
            )
        
        # Notify all team members
        for member in team.members.all():
            if member != user:  # Don't notify the requester
                NotificationService.send_notification(
                    user=member,
                    title=subject,
                    message=message,
                    category='team',
                    priority='normal',
                    send_email=False,  # Only notify organizer via email
                    send_in_app=True,
                    data={'team_id': team.id, 'join_request_id': join_request.id, 'action': 'join_request_received'}
                )

        return Response({
            'message': 'Join request sent successfully',
            'join_request': TeamJoinRequestSerializer(join_request).data
        }, status=201)


    @swagger_auto_schema(
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'team_id': openapi.Schema(type=openapi.TYPE_INTEGER, description='ID of the team'),
                'user_id': openapi.Schema(type=openapi.TYPE_INTEGER, description='ID of the user whose request to approve (optional)'),
                'join_request_id': openapi.Schema(type=openapi.TYPE_INTEGER, description='ID of the join request to approve (optional)'),
            },
            required=['team_id']
        ),
        responses={
            200: "Join request approved successfully",
            400: "Bad Request",
            403: "Forbidden - not team organizer",
            404: "Join request not found"
        },
        operation_description="Approve a team join request. Only team organizer can approve requests.",
        tags=['teams']
    )
    @action(detail=False, methods=['post'])
    def approve_join_request(self, request):
        if not request.user.is_authenticated:
            return Response({'error': 'Authentication required.'}, status=401)

        team_id = request.data.get('team_id')
        user_id = request.data.get('user_id')  # optional: the user whose request is being approved
        join_request_id = request.data.get('join_request_id')  # optional: specific join request ID

        if not team_id:
            return Response({'error': 'team_id is required'}, status=400)

        team = get_object_or_404(Team, id=team_id)

        # Check if user is organizer (using organizer field, not creator)
        if team.organizer != request.user:
            return Response({'error': 'Only the team organizer can approve requests.'}, status=403)

        # Get join request
        if join_request_id:
            join_request = TeamJoinRequest.objects.filter(id=join_request_id, team=team, status='pending').first()
        elif user_id:
            join_request = TeamJoinRequest.objects.filter(team=team, user_id=user_id, status='pending').first()
        else:
            join_request = TeamJoinRequest.objects.filter(team=team, status='pending').first()

        if not join_request:
            return Response({'error': 'No pending join request found for this team.'}, status=404)

        join_request.status = 'approved'
        join_request.save()
        team.members.add(join_request.user)

        # Update hackathon participant record
        from hackathon.models import HackathonParticipant
        try:
            participant = HackathonParticipant.objects.get(
                hackathon=team.hackathon,
                user=join_request.user
            )
            participant.team = team
            participant.looking_for_team = False
            participant.save()
        except HackathonParticipant.DoesNotExist:
            pass

        # Notify the requester
        user_name = (join_request.user.first_name + ' ' + join_request.user.last_name).strip() or join_request.user.username
        subject = f"Join Request Approved: {team.name}"
        message = f"Congratulations {user_name}!\n\nYour request to join the team '{team.name}' for '{team.hackathon.title}' has been approved.\n\nYou are now a member of the team!"
        
        NotificationService.send_notification(
            user=join_request.user,
            title=subject,
            message=message,
            category='team',
            priority='normal',
            send_email=True,
            send_in_app=True,
            data={'team_id': team.id, 'action': 'join_request_approved'}
        )

        # Notify team members
        organizer_name = (team.organizer.first_name + ' ' + team.organizer.last_name).strip() if team.organizer else 'Team Organizer'
        member_subject = f"New Member Joined: {team.name}"
        member_message = f"Dear Team,\n\n{user_name} has joined the team '{team.name}'.\n\nWelcome to the team!"
        
        for member in team.members.all():
            if member != join_request.user:  # Don't notify the new member
                NotificationService.send_notification(
                    user=member,
                    title=member_subject,
                    message=member_message,
                    category='team',
                    priority='normal',
                    send_email=False,
                    send_in_app=True,
                    data={'team_id': team.id, 'new_member_id': join_request.user.id, 'action': 'member_joined'}
                )

        return Response({
            'message': f'{join_request.user.username} has been added to the team.',
            'join_request': TeamJoinRequestSerializer(join_request).data,
            'team': TeamSerializer(team).data
        }, status=200)
        
    @swagger_auto_schema(
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'team_id': openapi.Schema(type=openapi.TYPE_INTEGER, description='ID of the team'),
                'user_id': openapi.Schema(type=openapi.TYPE_INTEGER, description='ID of the user whose request to reject (optional)'),
                'join_request_id': openapi.Schema(type=openapi.TYPE_INTEGER, description='ID of the join request to reject (optional)'),
            },
            required=['team_id']
        ),
        responses={
            200: "Join request rejected successfully",
            400: "Bad Request",
            403: "Forbidden - not team organizer",
            404: "Join request not found"
        },
        operation_description="Reject a team join request. Only team organizer can reject requests.",
        tags=['teams']
    )
    @action(detail=False, methods=['post'])
    def reject_join_request(self, request):
        if not request.user.is_authenticated:
            return Response({'error': 'Authentication required.'}, status=401)

        team_id = request.data.get('team_id')
        user_id = request.data.get('user_id')
        join_request_id = request.data.get('join_request_id')

        if not team_id:
            return Response({'error': 'team_id is required'}, status=400)

        team = get_object_or_404(Team, id=team_id)

        # Check if user is organizer (using organizer field, not creator)
        if team.organizer != request.user:
            return Response({'error': 'Only the team organizer can reject requests.'}, status=403)

        # Get join request
        if join_request_id:
            join_request = TeamJoinRequest.objects.filter(id=join_request_id, team=team, status='pending').first()
        elif user_id:
            join_request = TeamJoinRequest.objects.filter(team=team, user_id=user_id, status='pending').first()
        else:
            join_request = TeamJoinRequest.objects.filter(team=team, status='pending').first()

        if not join_request:
            return Response({'error': 'No pending join request found for this team.'}, status=404)

        join_request.status = 'rejected'
        join_request.save()

        # Notify the requester
        user_name = (join_request.user.first_name + ' ' + join_request.user.last_name).strip() or join_request.user.username
        subject = f"Join Request Update: {team.name}"
        message = f"Dear {user_name},\n\nYour request to join the team '{team.name}' for '{team.hackathon.title}' has been declined.\n\nYou can try joining another team or create your own team for this hackathon."
        
        NotificationService.send_notification(
            user=join_request.user,
            title=subject,
            message=message,
            category='team',
            priority='normal',
            send_email=True,
            send_in_app=True,
            data={'team_id': team.id, 'action': 'join_request_rejected'}
        )

        return Response({
            'message': f'{join_request.user.username} join request has been rejected.',
            'join_request': TeamJoinRequestSerializer(join_request).data
        }, status=200) 