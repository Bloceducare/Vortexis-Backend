from rest_framework import serializers
from rest_framework.exceptions import AuthenticationFailed

from accounts.models import User
from .models import Team


class CreateTeamSerializer(serializers.ModelSerializer):
    members = serializers.ListField(
        child=serializers.EmailField(),
        write_only=True,
        help_text="List of user emails to add as team members"
    )
    
    class Meta:
        model = Team
        fields = ['name', 'members']
    
    def validate(self, data):
        if not data.get('name'):
            raise serializers.ValidationError("Team name is required.")
        
        member_emails = data.get('members', [])
        if not member_emails:
            raise serializers.ValidationError("At least one member email is required.")
        
        if len(member_emails) != len(set(member_emails)):
            raise serializers.ValidationError("Duplicate member emails are not allowed.")
        
        # Validate all members exist
        member_users = []
        for email in member_emails:
            try:
                member = User.objects.get(email=email)
                member_users.append(member)
            except User.DoesNotExist:
                raise serializers.ValidationError(f"User with email {email} does not exist.")
        
        # Add the validated member users to data for use in create method
        data['member_users'] = member_users
        
        return data
    
    def create(self, validated_data):
        request = self.context.get('request')
        if not request:
            raise serializers.ValidationError("Request context is required.")
        
        user = request.user
        member_users = validated_data.pop('member_users')  # Get the validated User objects
        
        team = Team.objects.create(
            name=validated_data['name'],
            organizer=user
        )
        
        # Add members to team using the validated User objects
        team.members.set(member_users)
        return team


class TeamSerializer(serializers.ModelSerializer):
    organizer = serializers.SerializerMethodField()
    members = serializers.SerializerMethodField()
    hackathons = serializers.SerializerMethodField()
    projects = serializers.SerializerMethodField()
    submissions = serializers.SerializerMethodField()
    prizes = serializers.SerializerMethodField()

    class Meta:
        model = Team
        fields = ['id', 'name', 'organizer', 'members', 'hackathons', 'projects', 'submissions', 'prizes', 'created_at', 'updated_at']

    def get_organizer(self, obj):
        if obj.organizer:
            return {'id': obj.organizer.id, 'username': obj.organizer.username}
        return None

    def get_members(self, obj):
        return [{'id': member.id, 'username': member.username} for member in obj.members.all()]
    
    def get_hackathons(self, obj):
        return [{'id': hackathon.id, 'title': hackathon.title} for hackathon in obj.hackathons.all()]

    def get_projects(self, obj):
        return [{'id': project.id, 'title': project.title} for project in obj.get_projects()]
    
    def get_submissions(self, obj):
        return [{'id': submission.id, 'project_title': submission.project.title if submission.project else None} for submission in obj.get_submissions()]
    
    def get_prizes(self, obj):
        # Since there's no Prize model related to Team, return empty list
        return []


class UpdateTeamSerializer(serializers.ModelSerializer):
    class Meta:
        model = Team
        fields = ['name']

    def validate(self, data):
        request = self.context.get('request')
        if not request:
            raise serializers.ValidationError("Request context is required.")
        user = request.user
        team = self.instance
        if team.organizer != user:
            raise AuthenticationFailed("You are not authorized to update this team.")
        
        if not data.get('name'):
            raise serializers.ValidationError("Team name is required.")
        return data
    
    def update(self, instance, validated_data):
        instance.name = validated_data['name']
        instance.save()
        return instance


class AddMemberSerializer(serializers.Serializer):
    member_email = serializers.EmailField()

    def validate_member_email(self, value):
        request = self.context.get('request')
        if not request:
            raise serializers.ValidationError("Request context is required.")
        user = request.user
        team = self.instance
        if team and team.organizer != user:
            raise AuthenticationFailed("You are not authorized to add members to this team.")
        
        try:
            member = User.objects.get(email=value)
        except User.DoesNotExist:
            raise serializers.ValidationError("User with this email does not exist.")
        
        if member in team.members.all():
            raise serializers.ValidationError("User is already a member of this team.")
        
        return value
    
    def save(self):
        member = User.objects.get(email=self.validated_data['member_email'])
        self.instance.members.add(member)
        return self.instance


class RemoveMemberSerializer(serializers.Serializer):
    member_email = serializers.EmailField()

    def validate_member_email(self, value):
        request = self.context.get('request')
        if not request:
            raise serializers.ValidationError("Request context is required.")
        user = request.user
        team = self.instance
        if team.organizer != user:
            raise AuthenticationFailed("You are not authorized to remove members from this team.")
        
        try:
            member = User.objects.get(email=value)
        except User.DoesNotExist:
            raise serializers.ValidationError("User with this email does not exist.")
        
        if member not in team.members.all():
            raise serializers.ValidationError("User is not a member of this team.")
        
        if member == team.organizer:
            raise serializers.ValidationError("Cannot remove the team organizer.")
        
        return value
    
    def save(self):
        member = User.objects.get(email=self.validated_data['member_email'])
        self.instance.members.remove(member)
        return self.instance


class LeaveTeamSerializer(serializers.Serializer):
    """Serializer for users to leave a team"""
    
    def validate(self, data):
        request = self.context.get('request')
        if not request:
            raise serializers.ValidationError("Request context is required.")
        
        user = request.user
        team = self.instance
        
        if user not in team.members.all():
            raise serializers.ValidationError("You are not a member of this team.")
        
        if user == team.organizer:
            raise serializers.ValidationError("Team organizers cannot leave their own team. Transfer ownership or delete the team instead.")
        
        return data
    
    def save(self):
        user = self.context.get('request').user
        team = self.instance
        
        # Remove user from team
        team.members.remove(user)
        
        # Update hackathon participant records if team is registered for hackathons
        from hackathon.models import HackathonParticipant
        
        for hackathon in team.hackathons.all():
            try:
                participant = HackathonParticipant.objects.get(hackathon=hackathon, user=user)
                participant.team = None
                participant.looking_for_team = True
                participant.save()
            except HackathonParticipant.DoesNotExist:
                # User might not be registered for this hackathon, skip
                continue
        
        return team


class CreateHackathonTeamSerializer(serializers.ModelSerializer):
    hackathon_id = serializers.IntegerField(write_only=True)
    members = serializers.ListField(
        child=serializers.EmailField(),
        write_only=True,
        help_text="List of user emails to add as team members"
    )

    class Meta:
        model = Team
        fields = ['name', 'members', 'hackathon_id']
    
    def validate(self, data):
        from hackathon.models import Hackathon, HackathonParticipant
        
        request = self.context.get('request')
        if not request:
            raise serializers.ValidationError("Request context is required.")
        
        user = request.user
        hackathon_id = data.get('hackathon_id')
        
        if not data.get('name'):
            raise serializers.ValidationError("Team name is required.")
            
        member_emails = data.get('members', [])
        if not member_emails:
            raise serializers.ValidationError("At least one member email is required.")
            
        if len(member_emails) != len(set(member_emails)):
            raise serializers.ValidationError("Duplicate member emails are not allowed.")
        
        # Validate hackathon exists
        try:
            hackathon = Hackathon.objects.get(id=hackathon_id)
        except Hackathon.DoesNotExist:
            raise serializers.ValidationError("Hackathon does not exist.")
        
        # Check if team creator is registered for the hackathon
        if not HackathonParticipant.objects.filter(hackathon=hackathon, user=user).exists():
            raise serializers.ValidationError("You must be registered for this hackathon to create a team.")
        
        # Check if all members exist and are registered for the hackathon
        member_users = []
        for email in member_emails:
            try:
                member = User.objects.get(email=email)
                member_users.append(member)
                if not HackathonParticipant.objects.filter(hackathon=hackathon, user=member).exists():
                    raise serializers.ValidationError(f"User with email {email} is not registered for this hackathon.")
                # Check if member already has a team for this hackathon
                participant = HackathonParticipant.objects.get(hackathon=hackathon, user=member)
                if participant.has_team:
                    raise serializers.ValidationError(f"User with email {email} is already part of a team for this hackathon.")
            except User.DoesNotExist:
                raise serializers.ValidationError(f"User with email {email} does not exist.")
        
        # Add the validated member users to data for use in create method
        data['member_users'] = member_users
        
        # Check team size constraints
        team_size = len(member_emails)
        if team_size < hackathon.min_team_size or team_size > hackathon.max_team_size:
            raise serializers.ValidationError(f"Team size must be between {hackathon.min_team_size} and {hackathon.max_team_size} members.")
        
        return data
    
    def create(self, validated_data):
        from hackathon.models import Hackathon, HackathonParticipant
        
        hackathon_id = validated_data.pop('hackathon_id')
        member_users = validated_data.pop('member_users')  # Get the validated User objects
        validated_data.pop('members')  # Remove the emails list since we have User objects
        
        hackathon = Hackathon.objects.get(id=hackathon_id)
        request = self.context.get('request')
        user = request.user
        
        # Create team
        team = Team.objects.create(
            name=validated_data['name'],
            organizer=user
        )
        
        # Add members to team using the validated User objects
        team.members.set(member_users)
        
        # Register team for hackathon
        team.hackathons.add(hackathon)
        
        # Update participant records for all team members
        for member in team.members.all():
            participant = HackathonParticipant.objects.get(hackathon=hackathon, user=member)
            participant.team = team
            participant.looking_for_team = False
            participant.save()
        
        # Also update the organizer's participant record if they're not already in members
        organizer_participant = HackathonParticipant.objects.get(hackathon=hackathon, user=user)
        if organizer_participant.team != team:
            organizer_participant.team = team
            organizer_participant.looking_for_team = False
            organizer_participant.save()
        
        return team