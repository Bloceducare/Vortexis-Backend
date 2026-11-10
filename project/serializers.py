from rest_framework import serializers
from rest_framework.exceptions import AuthenticationFailed
from team.models import Team
from .models import Project
from hackathon.models import Submission


class CreateProjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = Project
        fields = ['title', 'description', 'github_url', 'live_link', 'demo_video_url', 'presentation_link', 'team', 'hackathon']
        extra_kwargs = {
            'hackathon': {'required': False},  # Optional when provided via URL
            'live_link': {'required': False, 'allow_blank': True},
            'demo_video_url': {'required': False, 'allow_blank': True},
            'presentation_link': {'required': False, 'allow_blank': True},
        }

    def to_internal_value(self, data):
        data = data.copy() if hasattr(data, 'copy') else dict(data)
        
        # If deliverables is passed as a dict: {"deliverables": {"github_url": "...", "demo_video_url": "..."}}
        deliverables = data.get('deliverables')
        if isinstance(deliverables, dict):
            for k, v in deliverables.items():
                if k not in data or not data[k]:
                    data[k] = v

        # Alias mappings for common frontend variations
        alias_map = {
            'demo_video_url': ['video_url', 'video_link', 'demo_url', 'demo_video', 'youtube_url', 'video'],
            'presentation_link': ['presentation_url', 'presentation', 'slides_url', 'slides_link', 'slides', 'pitch_deck', 'pitch_deck_url'],
            'github_url': ['github', 'github_link', 'repo_url', 'repository_url', 'git_url'],
            'live_link': ['live_url', 'demo_link', 'deployment_url', 'website_url', 'live_demo', 'app_url'],
        }
        for standard_field, aliases in alias_map.items():
            if not data.get(standard_field):
                for alias in aliases:
                    if data.get(alias):
                        data[standard_field] = data[alias]
                        break

        return super().to_internal_value(data)
    
    def validate(self, data):
        request = self.context.get('request')
        view = self.context.get('view')
        
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
        
        # Check if hackathon is provided via URL context or in data
        hackathon = None
        hackathon_id = None
        
        if view and hasattr(view, 'kwargs') and view.kwargs.get('hackathon_id'):
            # Hackathon provided via URL
            hackathon_id = view.kwargs.get('hackathon_id')
        elif data.get('hackathon'):
            # Hackathon provided in request data
            hackathon_id = data['hackathon'].id if hasattr(data['hackathon'], 'id') else data['hackathon']
        else:
            raise serializers.ValidationError("Hackathon is required.")
        
        try:
            team = Team.objects.get(id=data['team'].id if hasattr(data['team'], 'id') else data['team'])
        except Team.DoesNotExist:
            raise serializers.ValidationError("Team does not exist.")
        
        # Validate hackathon exists
        from hackathon.models import Hackathon
        try:
            hackathon = Hackathon.objects.get(id=hackathon_id)
        except Hackathon.DoesNotExist:
            raise serializers.ValidationError("Hackathon does not exist.")
        
        # Validate that team belongs to this hackathon
        if team.hackathon != hackathon:
            raise serializers.ValidationError("Team does not belong to this hackathon.")
        
        if team not in user.teams.all():
            raise serializers.ValidationError("You are not a member of this team.")
        
        # Check if team already has a project for this hackathon
        if Project.objects.filter(team=team, hackathon=hackathon).exists():
            raise serializers.ValidationError("Your team already has a project for this hackathon.")
        
        # Store hackathon for use in create method
        data['hackathon'] = hackathon
        
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
    hackathon = serializers.SerializerMethodField()
    is_submitted = serializers.SerializerMethodField()
    deliverables = serializers.SerializerMethodField()
    video_url = serializers.CharField(source='demo_video_url', read_only=True)
    presentation_url = serializers.CharField(source='presentation_link', read_only=True)
    
    class Meta:
        model = Project
        fields = [
            'id', 'title', 'description',
            'github_url', 'live_link', 'demo_video_url', 'presentation_link',
            'video_url', 'presentation_url', 'deliverables',
            'team', 'hackathon', 'is_submitted', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']
    
    def get_deliverables(self, obj):
        return {
            'github_url': obj.github_url or '',
            'live_link': obj.live_link or '',
            'demo_video_url': obj.demo_video_url or '',
            'presentation_link': obj.presentation_link or '',
            'video_url': obj.demo_video_url or '',
            'presentation_url': obj.presentation_link or '',
        }
    
    def get_team(self, obj):
        if obj.team:
            return {
                'id': obj.team.id,
                'name': obj.team.name
            }
        return None
    
    def get_hackathon(self, obj):
        if obj.hackathon:
            return {
                'id': obj.hackathon.id,
                'title': obj.hackathon.title,
                'start_date': obj.hackathon.start_date,
                'end_date': obj.hackathon.end_date,
                'currency': getattr(obj.hackathon, 'currency', 'USD') or 'USD'
            }
        return None

    def get_is_submitted(self, obj):
        # A Submission is linked OneToOne to Project; check existence
        try:
            return Submission.objects.filter(project=obj).exists()
        except Exception:
            return False


class UpdateProjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = Project
        fields = ['title', 'description', 'github_url', 'live_link', 'demo_video_url', 'presentation_link']
        extra_kwargs = {
            'title': {'required': False},
            'description': {'required': False},
            'github_url': {'required': False},
            'live_link': {'required': False, 'allow_blank': True},
            'demo_video_url': {'required': False, 'allow_blank': True},
            'presentation_link': {'required': False, 'allow_blank': True},
        }

    def to_internal_value(self, data):
        data = data.copy() if hasattr(data, 'copy') else dict(data)
        
        # If deliverables is passed as a dict: {"deliverables": {"github_url": "...", "demo_video_url": "..."}}
        deliverables = data.get('deliverables')
        if isinstance(deliverables, dict):
            for k, v in deliverables.items():
                if k not in data or not data[k]:
                    data[k] = v

        alias_map = {
            'demo_video_url': ['video_url', 'video_link', 'demo_url', 'demo_video', 'youtube_url', 'video'],
            'presentation_link': ['presentation_url', 'presentation', 'slides_url', 'slides_link', 'slides', 'pitch_deck', 'pitch_deck_url'],
            'github_url': ['github', 'github_link', 'repo_url', 'repository_url', 'git_url'],
            'live_link': ['live_url', 'demo_link', 'deployment_url', 'website_url', 'live_demo', 'app_url'],
        }
        for standard_field, aliases in alias_map.items():
            if not data.get(standard_field):
                for alias in aliases:
                    if data.get(alias):
                        data[standard_field] = data[alias]
                        break

        return super().to_internal_value(data)
    
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