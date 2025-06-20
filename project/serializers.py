from rest_framework import serializers
from rest_framework.exceptions import AuthenticationFailed
from team.models import Team
from .models import Project

class ProjectSerializer:
    class CreateProjectSerializer(serializers.ModelSerializer):
        class Meta:
            model = Project
            fields = ['title', 'description', 'github_url', 'live_link', 'demo_video_url', 'presentation_link', 'team']
            ref_name = 'ProjectCreateSerializer'
        
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
                team = Team.objects.get(id=data['team'])
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
            
            project = Project.objects.create(
                title=validated_data['title'],
                description=validated_data['description'],
                github_url=validated_data['github_url'],
                live_link=validated_data.get('live_link', ''),
                demo_video_url=validated_data.get('demo_video_url', ''),
                presentation_link=validated_data.get('presentation_link', ''),
                team=validated_data['team']
            )
            return project
    
    class ProjectSerializer(serializers.ModelSerializer):
        team = serializers.SerializerMethodField()
        
        class Meta:
            model = Project
            fields = ['id', 'title', 'description', 'github_url', 'live_link', 'demo_video_url', 'presentation_link', 'team', 'created_at', 'updated_at']
            read_only_fields = ['created_at', 'updated_at']
            ref_name = 'ProjectDetailSerializer'
        
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
            ref_name = 'ProjectUpdateSerializer'
        
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
            instance.title = validated_data.get('title', instance.title)
            instance.description = validated_data.get('description', instance.description)
            instance.github_url = validated_data.get('github_url', instance.github_url)
            instance.live_link = validated_data.get('live_link', instance.live_link)
            instance.demo_video_url = validated_data.get('demo_video_url', instance.demo_video_url)
            instance.presentation_link = validated_data.get('presentation_link', instance.presentation_link)
            instance.save()
            return instance 