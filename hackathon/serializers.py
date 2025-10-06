from rest_framework import serializers
from rest_framework.exceptions import AuthenticationFailed, ValidationError
from django.utils import timezone
from team.models import Team
from .models import Hackathon, Theme, Submission, Review, HackathonParticipant
from accounts.models import User
from utils.cloudinary_utils import upload_image_to_cloudinary


class ThemeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Theme
        fields = ['id', 'name', 'description', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at']

    def validate_name(self, value):
        return value.strip().lower()



class SubmitProjectSerializer(serializers.Serializer):
    hackathon_id = serializers.IntegerField()

    def validate_hackathon_id(self, value):
        request = self.context.get('request')
        if not request:
            raise serializers.ValidationError("Request context is required.")
        user = request.user
        try:
            hackathon = Hackathon.objects.get(id=value)
        except Hackathon.DoesNotExist:
            raise serializers.ValidationError("Hackathon does not exist.")
        return value

    def save(self, **kwargs):
        from project.models import Project
        project_id = self.context.get('project_id')
        project = Project.objects.get(id=project_id)
        hackathon = Hackathon.objects.get(id=self.validated_data['hackathon_id'])
        
        if Submission.objects.filter(project=project, hackathon=hackathon).exists():
            raise serializers.ValidationError("This project is already submitted to this hackathon.")
        if project.hackathon != hackathon:
            raise serializers.ValidationError("This project does not belong to this hackathon.")
        if project.team.hackathon != hackathon:
            raise serializers.ValidationError("Your team is not registered for this hackathon.")
        if hackathon.submission_deadline < timezone.now():
            raise serializers.ValidationError("Hackathon submission period has ended.")
        
        submission = Submission.objects.create(project=project, hackathon=hackathon, team=project.team)
        return submission


class SubmissionSerializer(serializers.ModelSerializer):
    project = serializers.SerializerMethodField()
    team = serializers.SerializerMethodField()
    reviews = serializers.SerializerMethodField()
    hackathon = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = Submission
        fields = ['id', 'project', 'team', 'hackathon', 'approved', 'status', 'reviews', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at', 'hackathon', 'project', 'team', 'reviews']

    def get_project(self, obj):
        return {
            'id': obj.project.id,
            'title': obj.project.title,
            'description': obj.project.description,
            'github_url': obj.project.github_url,
            'live_link': obj.project.live_link
        }

    def get_team(self, obj):
        return {'id': obj.team.id, 'name': obj.team.name}
    
    def get_reviews(self, obj):
        reviews = obj.reviews.all()
        return [
            {
                'id': review.id,
                'innovation_score': review.innovation_score,
                'technical_score': review.technical_score,
                'user_experience_score': review.user_experience_score,
                'impact_score': review.impact_score,
                'presentation_score': review.presentation_score,
                'overall_score': review.overall_score,
                'review': review.review,
                'judge': {
                    'id': review.judge.id,
                    'username': review.judge.username
                }
            }
            for review in reviews
        ]


class CreateSubmissionSerializer(serializers.ModelSerializer):
    project = serializers.IntegerField()

    class Meta:
        model = Submission
        fields = ['project']

    def validate_project(self, value):
        from project.models import Project
        request = self.context.get('request')
        user = request.user

        # Ensure value is an integer ID
        try:
            project_id = int(value)
        except (ValueError, TypeError):
            raise serializers.ValidationError("Project ID must be an integer.")

        try:
            project = Project.objects.get(id=project_id)
        except Project.DoesNotExist:
            raise serializers.ValidationError("Project does not exist.")

        if project.team not in user.teams.all():
            raise serializers.ValidationError("You are not a member of this project's team.")

        hackathon = self.context.get('hackathon')
        if project.hackathon != hackathon:
            raise serializers.ValidationError("This project does not belong to this hackathon.")

        if Submission.objects.filter(project=project, hackathon=hackathon).exists():
            raise serializers.ValidationError("This project is already submitted to this hackathon.")
        return project_id

    def create(self, validated_data):
        from project.models import Project
        hackathon = self.context.get('hackathon')
        project_id = validated_data['project']
        project = Project.objects.get(id=project_id)
        return Submission.objects.create(
            project=project,
            hackathon=hackathon,
            team=project.team,
            status='pending'  # Explicitly set to pending
        )


class UpdateSubmissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Submission
        fields = ['approved', 'status']

    def validate_approved(self, value):
        if not self.context['request'].user.is_organizer:
            raise serializers.ValidationError("Only organizers can update submission status.")
        return value
    
    def validate_status(self, value):
        if not self.context['request'].user.is_organizer:
            raise serializers.ValidationError("Only organizers can update submission status.")
        return value


class ReviewSerializer(serializers.ModelSerializer):
    judge = serializers.SerializerMethodField()
    submission = serializers.PrimaryKeyRelatedField(queryset=Submission.objects.all())
    hackathon_id = serializers.SerializerMethodField()

    class Meta:
        model = Review
        fields = ['id', 'submission', 'judge', 'hackathon_id', 'innovation_score', 'technical_score', 'user_experience_score', 'impact_score', 'presentation_score', 'overall_score', 'review', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at', 'judge']

    def get_judge(self, obj):
        return {'id': obj.judge.id, 'username': obj.judge.username}

    def get_hackathon_id(self, obj):
        return obj.submission.hackathon.id

    def validate(self, data):
        request = self.context.get('request')
        user = request.user
        submission = data['submission']
        if submission.hackathon not in user.judged_hackathons.all():
            raise serializers.ValidationError("You are not authorized to review this submission.")

        # Only check for duplicate reviews when creating (not updating)
        existing_review = Review.objects.filter(submission=submission, judge=user)
        if self.instance:
            # If updating, exclude the current instance
            existing_review = existing_review.exclude(pk=self.instance.pk)

        if existing_review.exists():
            raise serializers.ValidationError("You have already reviewed this submission.")

        # Validate all score fields are between 0 and 10
        for field in ['innovation_score', 'technical_score', 'user_experience_score', 'impact_score', 'presentation_score', 'overall_score']:
            value = data.get(field)
            if value is not None and (value < 0 or value > 10):
                raise serializers.ValidationError({field: "Score must be between 0 and 10."})
        return data


class HackathonSerializer(serializers.ModelSerializer):
    themes = ThemeSerializer(many=True, read_only=True)
    skills = serializers.SerializerMethodField()
    organization = serializers.SerializerMethodField()
    judges = serializers.SerializerMethodField()
    participants_count = serializers.SerializerMethodField()
    submissions_count = serializers.SerializerMethodField()

    class Meta:
        model = Hackathon
        fields = '__all__'


    def to_representation(self, instance):
        data = super().to_representation(instance)
        
        # Only include evaluation_criteria for judges and organizers
        request = self.context.get('request')
        if request and hasattr(request, 'user') and request.user.is_authenticated:
            user = request.user
            # Check if user is a judge for this hackathon or organizer of the hackathon
            is_judge = user in instance.judges.all()
            is_organizer = (instance.organization and 
                          (instance.organization.organizer == user or 
                           user in instance.organization.moderators.all()))
            
            if not (is_judge or is_organizer):
                data.pop('evaluation_criteria', None)
        else:
            # Remove evaluation_criteria for unauthenticated users
            data.pop('evaluation_criteria', None)
        
        return data

    def get_skills(self, obj):
        return [{'id': skill.id, 'name': skill.name} for skill in obj.skills.all()]
    
    def get_organization(self, obj):
        if obj.organization:
            return {
                'id': obj.organization.id,
                'name': obj.organization.name,
                'description': obj.organization.description,
                'is_approved': obj.organization.is_approved
            }
        return None
    
    def get_judges(self, obj):
        return [
            {
                'id': judge.id,
                'username': judge.username,
                'first_name': judge.first_name,
                'last_name': judge.last_name
            }
            for judge in obj.judges.all()
        ]
    
    def get_participants_count(self, obj):
        return obj.participants.count()
    
    def get_submissions_count(self, obj):
        return obj.submissions.count()


class CreateHackathonSerializer(HackathonSerializer):
    banner_image_file = serializers.ImageField(write_only=True, required=False)
    organization_id = serializers.IntegerField(write_only=True, required=True)

    class Meta(HackathonSerializer.Meta):
        fields = ['organization_id', 'title', 'description', 'banner_image', 'banner_image_file', 'visibility', 'venue', 'details', 'skills', 'themes', 'grand_prize', 'start_date', 'end_date', 'submission_deadline', 'min_team_size', 'max_team_size', 'rules', 'prizes', 'evaluation_criteria']
        extra_kwargs = {
            'banner_image': {'read_only': True}
        }

    def validate(self, data):
        request = self.context.get('request')
        if not request:
            raise serializers.ValidationError("Request context is required.")
        user = request.user
        if not user.is_organizer:
            raise serializers.ValidationError("Only organizers can create a hackathon.")

        # Validate that the provided organization belongs to the user and is approved
        organization_id = data.get('organization_id')
        if not organization_id:
            raise serializers.ValidationError("organization_id is required.")

        user_org = user.organizations.filter(id=organization_id, is_approved=True).first()
        if not user_org:
            raise serializers.ValidationError("Invalid organization or organization not approved.")

        if data.get('start_date') and data.get('end_date') and data['start_date'] > data['end_date']:
            raise serializers.ValidationError("Start date must be before end date.")
        if data.get('end_date') and data.get('submission_deadline') and data['submission_deadline'].date() > data['end_date']:
            raise serializers.ValidationError("Submission deadline must be before or on the end date.")
        if data.get('min_team_size') and data.get('max_team_size') and data['min_team_size'] > data['max_team_size']:
            raise serializers.ValidationError("Minimum team size cannot exceed maximum team size.")
        return data

    def create(self, validated_data):
        skills = validated_data.pop('skills', None)
        themes = validated_data.pop('themes', [])
        banner_image_file = validated_data.pop('banner_image_file', None)
        organization_id = validated_data.pop('organization_id')

        # Upload banner image to Cloudinary if provided
        if banner_image_file:
            banner_image_url = upload_image_to_cloudinary(banner_image_file, folder='hackathon_banners')
            validated_data['banner_image'] = banner_image_url

        from organization.models import Organization
        organization = Organization.objects.get(id=organization_id)

        hackathon = Hackathon.objects.create(
            **validated_data,
            organization=organization
        )
        if skills is not None:
            hackathon.skills.set(skills)
        hackathon.themes.set(themes)
        return hackathon

    def get_skills(self, obj):
        return [skill.name for skill in obj.skills.all()]


class UpdateHackathonSerializer(HackathonSerializer):
    banner_image_file = serializers.ImageField(write_only=True, required=False)
    
    class Meta(HackathonSerializer.Meta):
        fields = ['title', 'description', 'banner_image', 'banner_image_file', 'venue', 'details', 'skills', 'themes', 'grand_prize', 'start_date', 'end_date', 'submission_deadline', 'min_team_size', 'max_team_size', 'visibility', 'rules', 'prizes', 'evaluation_criteria']
        extra_kwargs = {field: {'required': False} for field in fields if field != 'banner_image'}
        extra_kwargs['banner_image'] = {'read_only': True}

    def validate(self, data):
        request = self.context.get('request')
        if not request:
            raise serializers.ValidationError("Request context is required.")
        user = request.user
        hackathon = self.instance
        if hackathon.organization.organizer != user and user not in hackathon.organization.moderators.all():
            raise serializers.ValidationError("You are not authorized to update this hackathon.")
        if data.get('start_date') and data.get('end_date') and data['start_date'] > data['end_date']:
            raise serializers.ValidationError("Start date must be before end date.")
        if data.get('end_date') and data.get('submission_deadline') and data['submission_deadline'].date() > data['end_date']:
            raise serializers.ValidationError("Submission deadline must be before or on the end date.")
        if data.get('min_team_size') and data.get('max_team_size') and data['min_team_size'] > data['max_team_size']:
            raise serializers.ValidationError("Minimum team size cannot exceed maximum team size.")
        return data

    def update(self, instance, validated_data):
        skills = validated_data.pop('skills', None)
        themes = validated_data.pop('themes', None)
        banner_image_file = validated_data.pop('banner_image_file', None)
        
        # Upload new banner image to Cloudinary if provided
        if banner_image_file:
            banner_image_url = upload_image_to_cloudinary(banner_image_file, folder='hackathon_banners')
            validated_data['banner_image'] = banner_image_url
        
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if skills is not None:
            instance.skills.set(skills)
        if themes is not None:
            instance.themes.set(themes)
        instance.save()
        return instance


class RegisterHackathonSerializer(serializers.Serializer):
    team_id = serializers.IntegerField()

    def validate_team_id(self, value):
        request = self.context.get('request')
        if not request:
            raise serializers.ValidationError("Request context is required.")
        user = request.user
        try:
            team = Team.objects.get(id=value)
        except Team.DoesNotExist:
            raise serializers.ValidationError("Team does not exist.")
        if user not in team.members.all():
            raise serializers.ValidationError("You are not a member of this team.")
        hackathon = self.instance
        # Check if team belongs to this hackathon (teams are now hackathon-specific)
        if team.hackathon != hackathon:
            raise serializers.ValidationError("This team is not associated with this hackathon.")
        # Since teams are now hackathon-specific, they are automatically "registered"
        if hackathon.start_date < timezone.now().date():
            raise serializers.ValidationError("Hackathon registration period has ended.")
        if team.members.count() < hackathon.min_team_size or team.members.count() > hackathon.max_team_size:
            raise serializers.ValidationError("Team size does not meet hackathon requirements.")
        
        # Check if all team members are individually registered for the hackathon
        for member in team.members.all():
            if not HackathonParticipant.objects.filter(hackathon=hackathon, user=member).exists():
                raise serializers.ValidationError(f"Team member {member.username} is not registered for this hackathon. All members must register individually first.")
        
        return value

    def update(self, instance, validated_data):
        team = Team.objects.get(id=validated_data['team_id'])
        # Team is already associated with hackathon via ForeignKey, no need to add
        
        # Update participant records for all team members
        for member in team.members.all():
            participant = HackathonParticipant.objects.get(hackathon=instance, user=member)
            participant.team = team
            participant.looking_for_team = False
            participant.save()
        
        return instance


class InviteJudgeSerializer(serializers.Serializer):
    emails = serializers.ListField(
        child=serializers.EmailField(),
        min_length=1,
        max_length=50,  # Reasonable limit for bulk invitations
        help_text="List of email addresses to invite as judges"
    )

    def validate_emails(self, value):
        from .models import JudgeInvitation
        
        hackathon = self.context.get('hackathon')
        errors = {}
        valid_emails = []
        
        for index, email in enumerate(value):
            email_errors = []
            
            # Check if user already exists and is already a judge for this hackathon
            try:
                user = User.objects.get(email=email)
                if user in hackathon.judges.all():
                    email_errors.append("User is already a judge for this hackathon.")
            except User.DoesNotExist:
                # User doesn't exist, which is fine - they'll be invited to sign up
                pass
            
            # Check if there's already a pending invitation for this email
            existing_invitation = JudgeInvitation.objects.filter(
                hackathon=hackathon, 
                email=email, 
                is_accepted=False
            ).first()
            
            if existing_invitation and existing_invitation.is_valid():
                email_errors.append("An invitation has already been sent to this email.")
            
            if email_errors:
                errors[f"email_{index}"] = email_errors
            else:
                valid_emails.append(email)
        
        if errors:
            raise serializers.ValidationError(errors)
            
        # Remove duplicates while preserving order
        seen = set()
        unique_emails = []
        for email in valid_emails:
            if email not in seen:
                seen.add(email)
                unique_emails.append(email)
        
        return unique_emails


class AcceptJudgeInvitationSerializer(serializers.Serializer):
    token = serializers.CharField()

    def validate_token(self, value):
        from .models import JudgeInvitation
        
        try:
            invitation = JudgeInvitation.objects.get(token=value)
            if not invitation.is_valid():
                raise serializers.ValidationError("Invitation token is invalid or expired.")
            return invitation
        except JudgeInvitation.DoesNotExist:
            raise serializers.ValidationError("Invalid invitation token.")


class HackathonParticipantSerializer(serializers.ModelSerializer):
    user = serializers.SerializerMethodField()
    team = serializers.SerializerMethodField()
    skills_offered = serializers.SerializerMethodField()

    class Meta:
        model = HackathonParticipant
        fields = ['id', 'user', 'team', 'looking_for_team', 'skills_offered', 'bio', 'has_team', 'created_at']
        read_only_fields = ['created_at', 'has_team']

    def get_user(self, obj):
        return {
            'id': obj.user.id,
            'username': obj.user.username,
            'first_name': obj.user.first_name,
            'last_name': obj.user.last_name
        }

    def get_team(self, obj):
        if obj.team:
            return {'id': obj.team.id, 'name': obj.team.name}
        return None

    def get_skills_offered(self, obj):
        return [{'id': skill.id, 'name': skill.name} for skill in obj.skills_offered.all()]


class IndividualRegistrationSerializer(serializers.Serializer):
    bio = serializers.CharField(max_length=500, required=False, allow_blank=True)
    skills_offered = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        allow_empty=True
    )

    def validate_skills_offered(self, value):
        from accounts.models import Skill
        if value:
            existing_skills = Skill.objects.filter(id__in=value)
            if len(existing_skills) != len(value):
                raise serializers.ValidationError("One or more skills do not exist.")
        return value

    def validate(self, data):
        request = self.context.get('request')
        if not request:
            raise serializers.ValidationError("Request context is required.")
        
        user = request.user
        hackathon = self.context.get('hackathon')
        
        if not hackathon:
            raise serializers.ValidationError("Hackathon context is required.")
        
        if HackathonParticipant.objects.filter(hackathon=hackathon, user=user).exists():
            raise serializers.ValidationError("You are already registered for this hackathon.")
        
        if hackathon.start_date < timezone.now().date():
            raise serializers.ValidationError("Hackathon registration period has ended.")
        
        return data

    def create(self, validated_data):
        from accounts.models import Skill
        
        skills_offered = validated_data.pop('skills_offered', [])
        hackathon = self.context.get('hackathon')
        user = self.context.get('request').user
        
        participant = HackathonParticipant.objects.create(
            hackathon=hackathon,
            user=user,
            bio=validated_data.get('bio', ''),
            looking_for_team=True
        )
        
        if skills_offered:
            skills = Skill.objects.filter(id__in=skills_offered)
            participant.skills_offered.set(skills)
        
        return participant


class JoinTeamSerializer(serializers.Serializer):
    team_id = serializers.IntegerField()

    def validate_team_id(self, value):
        request = self.context.get('request')
        hackathon = self.context.get('hackathon')
        
        try:
            team = Team.objects.get(id=value)
        except Team.DoesNotExist:
            raise serializers.ValidationError("Team does not exist.")
        
        # Check if team belongs to this hackathon (teams are now hackathon-specific)
        if team.hackathon != hackathon:
            raise serializers.ValidationError("This team does not belong to this hackathon.")
        
        # Check if team has space
        if team.members.count() >= hackathon.max_team_size:
            raise serializers.ValidationError("This team is already at maximum capacity.")
        
        return value

    def validate(self, data):
        request = self.context.get('request')
        hackathon = self.context.get('hackathon')
        user = request.user
        
        # Check if user is registered as individual participant
        try:
            participant = HackathonParticipant.objects.get(hackathon=hackathon, user=user)
        except HackathonParticipant.DoesNotExist:
            raise serializers.ValidationError("You must register for the hackathon first before joining a team.")
        
        # Check if user already has a team
        if participant.has_team:
            raise serializers.ValidationError("You are already part of a team for this hackathon.")
        
        return data

    def save(self):
        team = Team.objects.get(id=self.validated_data['team_id'])
        hackathon = self.context.get('hackathon')
        user = self.context.get('request').user
        
        # Add user to team
        team.members.add(user)
        
        # Update participant record
        participant = HackathonParticipant.objects.get(hackathon=hackathon, user=user)
        participant.team = team
        participant.looking_for_team = False
        participant.save()
        
        return participant