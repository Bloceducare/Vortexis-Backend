from rest_framework import serializers
from rest_framework.exceptions import AuthenticationFailed
from team.models import Team
from .models import Project


class CreateProjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = Project
        fields = ['title', 'description', 'github_url', 'live_link', 'demo_video_url', 'presentation_link', 'team']
    
    def validate(self, data):
        request = self.context.get('request')
        if not request:
            raise serializers.ValidationError("Request context is required.")
        
        user = request.user
        if not user.is_authenticated:
            raise AuthenticationFailed("You are not authenticated.")
        
        if not data.get('title'):
            raise serializers.ValidationError("Title is required.")
        if not data.get('description'):
            raise serializers.ValidationError("Description is required.")
        if not data.get('github_url'):
            raise serializers.ValidationError("Github url is required.")
        if not data.get('team'):
            raise serializers.ValidationError("Team is required.")
        
        try:
            team = Team.objects.get(id=data['team'].id if hasattr(data['team'], 'id') else data['team'])
        except Team.DoesNotExist:
            raise serializers.ValidationError("Team does not exist.")
        
        if team not in user.teams.all():
            raise serializers.ValidationError("You are not a member of this team.")
        
        return data
    
    def create(self, validated_data):
        request = self.context.get('request')
        user = request.user
        if not user.is_authenticated:
            raise AuthenticationFailed("You are not authenticated.")
        
        project = Project.objects.create(**validated_data)
        return project


class ProjectSerializer(serializers.ModelSerializer):
    team = serializers.SerializerMethodField()
    
    class Meta:
        model = Project
        fields = ['id', 'title', 'description', 'github_url', 'live_link', 'demo_video_url', 'presentation_link', 'team', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at']
    
    def get_team(self, obj):
        if obj.team:
            return {
                'id': obj.team.id,
                'name': obj.team.name
            }
        return None


class UpdateProjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = Project
        fields = ['title', 'description', 'github_url', 'live_link', 'demo_video_url', 'presentation_link']
        extra_kwargs = {
            'title': {'required': False},
            'description': {'required': False},
            'github_url': {'required': False},
            'live_link': {'required': False},
            'demo_video_url': {'required': False},
            'presentation_link': {'required': False},
        }
    
    def validate(self, data):
        request = self.context.get('request')
        if not request:
            raise serializers.ValidationError("Request context is required.")
        
        user = request.user
        if not user.is_authenticated:
            raise AuthenticationFailed("You are not authenticated.")
        
        team = self.instance.team
        if team not in user.teams.all():
            raise serializers.ValidationError("You are not a member of this team.")
        
        return data
    
    def update(self, instance, validated_data):
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance 