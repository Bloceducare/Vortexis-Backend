from rest_framework import serializers
from rest_framework.exceptions import AuthenticationFailed

from accounts.models import User
from .models import Team


class CreateTeamSerializer(serializers.ModelSerializer):
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
        team.members.set(validated_data['members'])
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
        return [{'id': project.id, 'title': project.title} for project in obj.projects.all()]
    
    def get_submissions(self, obj):
        return [{'id': submission.id, 'project_title': submission.project.title} for submission in obj.submissions.all()]
    
    def get_prizes(self, obj):
        return [{'id': prize.id, 'name': prize.name, 'amount': prize.amount} for prize in obj.prizes.all()]


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
    