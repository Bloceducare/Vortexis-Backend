from rest_framework import serializers
from rest_framework.exceptions import AuthenticationFailed, ValidationError
from django.utils import timezone
from team.models import Team
from .models import Hackathon, Theme, Submission, Review, HackathonParticipant
from accounts.models import User, Skill


class ThemeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Theme
        fields = ['id', 'name', 'description', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at']

    def validate_name(self, value):
        return value.strip().lower()



class SubmitProjectSerializer(serializers.Serializer):
    project_id = serializers.IntegerField()

    def validate_project_id(self, value):
        from project.models import Project
        request = self.context.get('request')
        if not request:
            raise serializers.ValidationError("Request context is required.")

        user = request.user
        try:
            project = Project.objects.select_related('team', 'hackathon').get(id=value)
        except Project.DoesNotExist:
            raise serializers.ValidationError("Project does not exist.")

        # Check if user is a member of the project's team
        if not project.team.members.filter(id=user.id).exists():
            raise serializers.ValidationError("You are not a member of this project's team.")

        return value

    def validate(self, attrs):
        from project.models import Project
        project_id = attrs['project_id']
        hackathon_id = self.context.get('hackathon_id')

        if not hackathon_id:
            raise serializers.ValidationError("Hackathon ID is required in context.")

        try:
            project = Project.objects.select_related('team', 'hackathon').get(id=project_id)
            hackathon = Hackathon.objects.get(id=hackathon_id)
        except Project.DoesNotExist:
            raise serializers.ValidationError("Project does not exist.")
        except Hackathon.DoesNotExist:
            raise serializers.ValidationError("Hackathon does not exist.")

        # Validation checks
        if Submission.objects.filter(project=project, hackathon=hackathon).exists():
            raise serializers.ValidationError("This project is already submitted to this hackathon.")

        if project.hackathon != hackathon:
            raise serializers.ValidationError("This project does not belong to this hackathon.")

        if project.team.hackathon != hackathon:
            raise serializers.ValidationError("Your team is not registered for this hackathon.")

        if hackathon.submission_deadline and hackathon.submission_deadline < timezone.now():
            raise serializers.ValidationError("Hackathon submission period has ended.")

        return attrs

    def save(self, **kwargs):
        from project.models import Project
        project_id = self.validated_data['project_id']
        hackathon_id = self.context.get('hackathon_id')

        project = Project.objects.select_related('team', 'hackathon').get(id=project_id)
        hackathon = Hackathon.objects.get(id=hackathon_id)

        # Update deliverables if provided directly in the submission request
        request = self.context.get('request')
        if request and hasattr(request, 'data'):
            data = request.data
            delivs = data.get('deliverables') if isinstance(data.get('deliverables'), dict) else data

            github = delivs.get('github_url') or delivs.get('github') or delivs.get('repo_url')
            live = delivs.get('live_link') or delivs.get('live_url') or delivs.get('demo_link')
            video = (delivs.get('demo_video_url') or delivs.get('video_url') or 
                     delivs.get('video_link') or delivs.get('demo_url'))
            pres = (delivs.get('presentation_link') or delivs.get('presentation_url') or 
                    delivs.get('slides_url') or delivs.get('pitch_deck'))

            updated = False
            if github and project.github_url != github:
                project.github_url = github
                updated = True
            if live and project.live_link != live:
                project.live_link = live
                updated = True
            if video and project.demo_video_url != video:
                project.demo_video_url = video
                updated = True
            if pres and project.presentation_link != pres:
                project.presentation_link = pres
                updated = True
            if updated:
                project.save()

        submission = Submission.objects.create(project=project, hackathon=hackathon, team=project.team)
        return submission


class SubmissionSerializer(serializers.ModelSerializer):
    project = serializers.SerializerMethodField()
    team = serializers.SerializerMethodField()
    reviews = serializers.SerializerMethodField()
    hackathon = serializers.PrimaryKeyRelatedField(read_only=True)
    currency = serializers.SerializerMethodField()

    class Meta:
        model = Submission
        fields = ['id', 'project', 'team', 'hackathon', 'currency', 'approved', 'status', 'reviews', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at', 'hackathon', 'currency', 'project', 'team', 'reviews']

    def get_currency(self, obj):
        if obj.hackathon:
            return getattr(obj.hackathon, 'currency', 'USD') or 'USD'
        return 'USD'

    def get_project(self, obj):
        if not obj.project:
            return None
        return {
            'id': obj.project.id,
            'title': obj.project.title,
            'description': obj.project.description,
            'github_url': obj.project.github_url or '',
            'live_link': obj.project.live_link or '',
            'demo_video_url': obj.project.demo_video_url or '',
            'presentation_link': obj.project.presentation_link or '',
            'video_url': obj.project.demo_video_url or '',
            'presentation_url': obj.project.presentation_link or '',
            'deliverables': {
                'github_url': obj.project.github_url or '',
                'live_link': obj.project.live_link or '',
                'demo_video_url': obj.project.demo_video_url or '',
                'presentation_link': obj.project.presentation_link or '',
                'video_url': obj.project.demo_video_url or '',
                'presentation_url': obj.project.presentation_link or '',
            },
            'created_at': obj.project.created_at,
            'updated_at': obj.project.updated_at
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

        # Update deliverables if provided in request
        request = self.context.get('request')
        if request and hasattr(request, 'data'):
            data = request.data
            delivs = data.get('deliverables') if isinstance(data.get('deliverables'), dict) else data

            github = delivs.get('github_url') or delivs.get('github') or delivs.get('repo_url')
            live = delivs.get('live_link') or delivs.get('live_url') or delivs.get('demo_link')
            video = (delivs.get('demo_video_url') or delivs.get('video_url') or 
                     delivs.get('video_link') or delivs.get('demo_url'))
            pres = (delivs.get('presentation_link') or delivs.get('presentation_url') or 
                    delivs.get('slides_url') or delivs.get('pitch_deck'))

            updated = False
            if github and project.github_url != github:
                project.github_url = github
                updated = True
            if live and project.live_link != live:
                project.live_link = live
                updated = True
            if video and project.demo_video_url != video:
                project.demo_video_url = video
                updated = True
            if pres and project.presentation_link != pres:
                project.presentation_link = pres
                updated = True
            if updated:
                project.save()

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
        extra_kwargs = {
            'innovation_score': {'required': False, 'default': 0},
            'technical_score': {'required': False, 'default': 0},
            'user_experience_score': {'required': False, 'default': 0},
            'impact_score': {'required': False, 'default': 0},
            'presentation_score': {'required': False, 'default': 0},
            'overall_score': {'required': False},
            'review': {'required': False, 'allow_blank': True},
        }

    def to_internal_value(self, data):
        data = data.copy() if hasattr(data, 'copy') else dict(data)
        
        # Accept submission_id as submission
        if not data.get('submission') and data.get('submission_id'):
            data['submission'] = data.get('submission_id')

        # Accept comment / feedback aliases
        if not data.get('review') and (data.get('feedback') or data.get('comment') or data.get('comments')):
            data['review'] = data.get('feedback') or data.get('comment') or data.get('comments')

        # Accept ux_score alias
        if not data.get('user_experience_score') and data.get('ux_score'):
            data['user_experience_score'] = data.get('ux_score')

        return super().to_internal_value(data)

    def get_judge(self, obj):
        return {
            'id': obj.judge.id,
            'username': obj.judge.username,
            'first_name': obj.judge.first_name,
            'last_name': obj.judge.last_name,
        }

    def get_hackathon_id(self, obj):
        return obj.submission.hackathon.id

    def validate(self, data):
        request = self.context.get('request')
        user = request.user
        submission = data['submission']

        # Check if user is a registered judge for this hackathon
        is_assigned_judge = (
            submission.hackathon in user.judged_hackathons.all() or
            user in submission.hackathon.judges.all() or
            user.is_admin
        )
        if not is_assigned_judge:
            raise serializers.ValidationError("You are not authorized as a judge for this hackathon.")

        # Only check for duplicate reviews when creating (not updating)
        existing_review = Review.objects.filter(submission=submission, judge=user)
        if self.instance:
            existing_review = existing_review.exclude(pk=self.instance.pk)

        if existing_review.exists():
            raise serializers.ValidationError("You have already reviewed this submission. Use PUT/PATCH to update your review.")

        # If overall_score is not passed, automatically compute the average of the 5 criteria
        sub_criteria = ['innovation_score', 'technical_score', 'user_experience_score', 'impact_score', 'presentation_score']
        for field in sub_criteria:
            if field not in data or data.get(field) is None:
                data[field] = 0

        if 'overall_score' not in data or data.get('overall_score') is None:
            scores = [data[f] for f in sub_criteria]
            data['overall_score'] = round(sum(scores) / len(scores)) if scores else 0

        # Validate all score fields are between 0 and 10
        all_score_fields = sub_criteria + ['overall_score']
        for field in all_score_fields:
            value = data.get(field)
            if value is not None and (value < 0 or value > 10):
                raise serializers.ValidationError({field: "Score must be an integer between 0 and 10."})

        return data


class HackathonSerializer(serializers.ModelSerializer):
    themes = ThemeSerializer(many=True, read_only=True)
    skills = serializers.SerializerMethodField()
    organization = serializers.SerializerMethodField()
    judges = serializers.SerializerMethodField()
    participants_count = serializers.SerializerMethodField()
    submissions_count = serializers.SerializerMethodField()
    teams_count = serializers.SerializerMethodField()

    class Meta:
        model = Hackathon
        fields = '__all__'
        ref_name = 'HackathonDetailSerializer'


    def to_representation(self, instance):
        data = super().to_representation(instance)
        
        # Always guarantee currency is returned (fallback to USD)
        if not data.get('currency'):
            data['currency'] = getattr(instance, 'currency', 'USD') or 'USD'
        
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
        return obj.participants_count
    
    def get_teams_count(self, obj):
        return obj.teams.count()
    
    def get_submissions_count(self, obj):
        return obj.submissions.count()


def _required_messages(label):
    """User-facing messages for a required field, keyed by DRF error code."""
    return {
        'required': f"{label} is required.",
        'blank': f"{label} cannot be empty.",
        'null': f"{label} is required.",
    }


class CreateHackathonSerializer(HackathonSerializer):
    banner_image_file = serializers.URLField(
        write_only=True, required=False, allow_blank=True, allow_null=True,
        error_messages={'invalid': "Banner image must be a valid URL. Please re-upload the image."},
    )
    organization_id = serializers.IntegerField(
        write_only=True, required=True,
        error_messages={
            **_required_messages("Organization"),
            'invalid': "Organization is invalid. Please select an organization and try again.",
        },
    )
    # Overrides the read-only SerializerMethodField inherited from HackathonSerializer,
    # which previously caused selected skills to be silently dropped on create.
    skills = serializers.PrimaryKeyRelatedField(
        many=True, required=False, queryset=Skill.objects.all(),
        error_messages={'does_not_exist': "One of the selected skills no longer exists. Please refresh the skills list."},
    )
    currency = serializers.CharField(
        max_length=10, required=False, default="USD", allow_blank=True,
        error_messages={'max_length': "Currency code must be at most {max_length} characters."},
    )

    class Meta(HackathonSerializer.Meta):
        fields = ['organization_id', 'title', 'description', 'banner_image', 'banner_image_file', 'visibility', 'venue', 'details', 'skills', 'themes', 'grand_prize', 'currency', 'start_date', 'end_date', 'submission_deadline', 'min_team_size', 'max_team_size', 'rules', 'prizes', 'evaluation_criteria']
        extra_kwargs = {
            'banner_image': {'read_only': True},
            'title': {'error_messages': {
                **_required_messages("Hackathon name"),
                'max_length': "Hackathon name must be at most {max_length} characters.",
            }},
            'description': {'error_messages': _required_messages("Description")},
            'venue': {'error_messages': {
                **_required_messages("Venue / location"),
                'max_length': "Venue / location must be at most {max_length} characters.",
            }},
            'start_date': {'error_messages': {
                **_required_messages("Start date"),
                'invalid': "Start date is not a valid date (expected YYYY-MM-DD).",
            }},
            'end_date': {'error_messages': {
                **_required_messages("End date"),
                'invalid': "End date is not a valid date (expected YYYY-MM-DD).",
            }},
            'submission_deadline': {'error_messages': {
                **_required_messages("Submission deadline"),
                'invalid': "Submission deadline is not a valid date.",
            }},
            'min_team_size': {'error_messages': {
                'invalid': "Minimum team size must be a whole number.",
                'min_value': "Minimum team size must be at least {min_value}.",
                'max_value': "Minimum team size cannot be more than {max_value}.",
            }},
            'max_team_size': {'error_messages': {
                'invalid': "Maximum team size must be a whole number.",
                'min_value': "Maximum team size must be at least {min_value}.",
                'max_value': "Maximum team size cannot be more than {max_value}.",
            }},
            'grand_prize': {'error_messages': {
                'invalid': "Total prize pool must be a whole number.",
                'max_value': "Total prize pool is too large.",
            }},
        }

    def validate_title(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Hackathon name cannot be empty.")
        return value

    def validate_venue(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Venue / location cannot be empty.")
        return value

    def validate_grand_prize(self, value):
        if value is not None and value < 0:
            raise serializers.ValidationError("Total prize pool cannot be negative.")
        return value

    def validate(self, data):
        request = self.context.get('request')
        if not request:
            raise serializers.ValidationError("Request context is required.")
        user = request.user
        if not user.is_organizer:
            raise serializers.ValidationError("Only organizers can create a hackathon.")

        # Validate that the provided organization belongs to the user and is approved
        organization_id = data.get('organization_id')
        from organization.models import Organization
        org = Organization.objects.filter(id=organization_id).first() if organization_id else None
        if not org:
            raise serializers.ValidationError({"organization_id": "No organization selected, or it no longer exists. Please select an organization from your dashboard and try again."})
        if org.organizer != user:
            raise serializers.ValidationError({"organization_id": f"Organization '{org.name}' does not belong to your account."})
        if not org.is_approved:
            raise serializers.ValidationError({"organization_id": f"Organization '{org.name}' is pending administrator approval. Hackathons can only be created once the organization is approved."})

        # Collect all cross-field problems at once so the user can fix them in one pass.
        errors = {}
        start_date = data.get('start_date')
        end_date = data.get('end_date')
        deadline = data.get('submission_deadline')

        if start_date and start_date < timezone.localdate():
            errors['start_date'] = "Start date cannot be in the past."
        if start_date and end_date and start_date > end_date:
            errors['end_date'] = "End date must be on or after the start date."
        if deadline:
            deadline_date = timezone.localtime(deadline).date() if timezone.is_aware(deadline) else deadline.date()
            if end_date and deadline_date > end_date:
                errors['submission_deadline'] = "Submission deadline must be on or before the end date."
            elif start_date and deadline_date < start_date:
                errors['submission_deadline'] = "Submission deadline must be on or after the start date."

        min_size = data.get('min_team_size')
        max_size = data.get('max_team_size')
        if min_size and max_size and min_size > max_size:
            errors['max_team_size'] = "Maximum team size must be greater than or equal to the minimum team size."

        if errors:
            raise serializers.ValidationError(errors)
        return data

    def create(self, validated_data):
        skills = validated_data.pop('skills', None)
        themes = validated_data.pop('themes', [])
        banner_image_url = validated_data.pop('banner_image_file', None)
        organization_id = validated_data.pop('organization_id')

        # Set banner image URL if provided
        if banner_image_url:
            validated_data['banner_image'] = banner_image_url

        from organization.models import Organization
        organization = Organization.objects.get(id=organization_id)

        if not validated_data.get('currency'):
            validated_data['currency'] = 'USD'

        hackathon = Hackathon.objects.create(
            **validated_data,
            organization=organization
        )
        if skills is not None:
            hackathon.skills.set(skills)
        hackathon.themes.set(themes)
        return hackathon


class UpdateHackathonSerializer(HackathonSerializer):
    banner_image_file = serializers.URLField(write_only=True, required=False, allow_blank=True)
    currency = serializers.CharField(max_length=10, required=False, allow_blank=True)
    
    class Meta(HackathonSerializer.Meta):
        fields = ['title', 'description', 'banner_image', 'banner_image_file', 'venue', 'details', 'skills', 'themes', 'grand_prize', 'currency', 'start_date', 'end_date', 'submission_deadline', 'min_team_size', 'max_team_size', 'visibility', 'rules', 'prizes', 'evaluation_criteria']
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
        banner_image_url = validated_data.pop('banner_image_file', None)
        
        # Set new banner image URL if provided
        if banner_image_url:
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