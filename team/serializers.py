from rest_framework import serializers
from rest_framework.exceptions import AuthenticationFailed

from accounts.models import User
from .models import Team


class CreateTeamSerializer(serializers.ModelSerializer):
    members = serializers.ListField(
        child=serializers.IntegerField(),
        write_only=True,
        help_text="List of user IDs to add as team members"
    )
    
    class Meta:
        model = Team
        fields = ['name', 'members']
    
    def validate(self, data):
        if not data.get('name'):
            raise serializers.ValidationError("Team name is required.")
        if not data.get('members'):
            raise serializers.ValidationError("At least one member is required.")
        members = data.get('members')
        if len(members) != len(set(members)):
            raise serializers.ValidationError("Duplicate members are not allowed.")
        return data
    
    def create(self, validated_data):
        request = self.context.get('request')
        if not request:
            raise serializers.ValidationError("Request context is required.")
        
        user = request.user
        
        team = Team.objects.create(
            name=validated_data['name'],
            organizer=user
        )
        # Ensure members are User objects, not IDs
        member_ids = validated_data['members']
        members = User.objects.filter(id__in=member_ids)
        team.members.set(members)
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
    member_id = serializers.IntegerField()

    def validate_member_id(self, value):
        request = self.context.get('request')
        if not request:
            raise serializers.ValidationError("Request context is required.")
        user = request.user
        team = self.instance
        if team and team.organizer != user:
            raise AuthenticationFailed("You are not authorized to add members to this team.")
        
        try:
            member = User.objects.get(id=value)
        except User.DoesNotExist:
            raise serializers.ValidationError("User does not exist.")
        
        if member in team.members.all():
            raise serializers.ValidationError("User is already a member of this team.")
        
        return value
    
    def save(self):
        member = User.objects.get(id=self.validated_data['member_id'])
        self.instance.members.add(member)
        return self.instance


class RemoveMemberSerializer(serializers.Serializer):
    member_id = serializers.IntegerField()

    def validate_member_id(self, value):
        request = self.context.get('request')
        if not request:
            raise serializers.ValidationError("Request context is required.")
        user = request.user
        team = self.instance
        if team.organizer != user:
            raise AuthenticationFailed("You are not authorized to remove members from this team.")
        
        try:
            member = User.objects.get(id=value)
        except User.DoesNotExist:
            raise serializers.ValidationError("User does not exist.")
        
        if member not in team.members.all():
            raise serializers.ValidationError("User is not a member of this team.")
        
        if member == team.organizer:
            raise serializers.ValidationError("Cannot remove the team organizer.")
        
        return value
    
    def save(self):
        member = User.objects.get(id=self.validated_data['member_id'])
        self.instance.members.remove(member)
        return self.instance


class CreateHackathonTeamSerializer(serializers.ModelSerializer):
    hackathon_id = serializers.IntegerField(write_only=True)
    members = serializers.ListField(
        child=serializers.IntegerField(),
        write_only=True,
        help_text="List of user IDs to add as team members"
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
            
        members = data.get('members', [])
        if not members:
            raise serializers.ValidationError("At least one member is required.")
            
        if len(members) != len(set(members)):
            raise serializers.ValidationError("Duplicate members are not allowed.")
        
        # Validate hackathon exists
        try:
            hackathon = Hackathon.objects.get(id=hackathon_id)
        except Hackathon.DoesNotExist:
            raise serializers.ValidationError("Hackathon does not exist.")
        
        # Check if team creator is registered for the hackathon
        if not HackathonParticipant.objects.filter(hackathon=hackathon, user=user).exists():
            raise serializers.ValidationError("You must be registered for this hackathon to create a team.")
        
        # Check if all members are registered for the hackathon
        for member_id in members:
            try:
                member = User.objects.get(id=member_id)
                if not HackathonParticipant.objects.filter(hackathon=hackathon, user=member).exists():
                    raise serializers.ValidationError(f"User {member.username} is not registered for this hackathon.")
                # Check if member already has a team for this hackathon
                participant = HackathonParticipant.objects.get(hackathon=hackathon, user=member)
                if participant.has_team:
                    raise serializers.ValidationError(f"User {member.username} is already part of a team for this hackathon.")
            except User.DoesNotExist:
                raise serializers.ValidationError(f"User with id {member_id} does not exist.")
        
        # Check team size constraints
        team_size = len(members)
        if team_size < hackathon.min_team_size or team_size > hackathon.max_team_size:
            raise serializers.ValidationError(f"Team size must be between {hackathon.min_team_size} and {hackathon.max_team_size} members.")
        
        return data
    
    def create(self, validated_data):
        from hackathon.models import Hackathon, HackathonParticipant
        
        hackathon_id = validated_data.pop('hackathon_id')
        hackathon = Hackathon.objects.get(id=hackathon_id)
        request = self.context.get('request')
        user = request.user
        
        # Create team
        team = Team.objects.create(
            name=validated_data['name'],
            organizer=user
        )
        # Ensure members are User objects, not IDs
        member_ids = validated_data['members']
        members = User.objects.filter(id__in=member_ids)
        team.members.set(members)
        
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