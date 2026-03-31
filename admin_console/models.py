from django.db import models
import pyotp
from django.contrib.auth.models import AbstractUser, Group, Permission
from django.core.validators import MinValueValidator, MaxValueValidator, URLValidator
from django.utils import timezone
from datetime import timedelta
import secrets

# Custom user with roles
class User(AbstractUser):
    ROLE_CHOICES = [
        ('PlatformOwner','Platform Owner'),
        ('SystemAdmin','System Admin'),
        ('Organizer','Organizer'),
        ('Judge','Judge'),
        ('Participant','Participant')
    ]
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    status = models.CharField(max_length=10, choices=[('active','Active'),('inactive','Inactive')], default='active')
    
    # 2FA secret (stored securely)
    totp_secret = models.CharField(max_length=16, blank=True, null=True)
    
    groups = models.ManyToManyField(Group, related_name='admin_console_user_set', blank=True)
    user_permissions = models.ManyToManyField(Permission, related_name='admin_console_user_permission_set', blank=True)

    def generate_totp_secret(self):
        self.totp_secret = pyotp.random_base32()
        self.save()

    def verify_totp(self, token):
        if not self.totp_secret:
            return False
        totp = pyotp.TOTP(self.totp_secret)
        return totp.verify(token)
  

class Skill(models.Model):
    name = models.CharField(max_length=50, null=False, blank=False)

    def __str__(self):
        return self.name


class Organization(models.Model):
    name = models.CharField(max_length=128, unique=True)
    description = models.TextField(default="No description provided.")
    website = models.URLField(max_length=200, blank=True, null=True, validators=[URLValidator()])
    logo = models.URLField(max_length=500, blank=True, null=True)
    location = models.CharField(max_length=32, blank=True, null=True)
    tagline = models.CharField(max_length=200, blank=True, null=True)
    about = models.TextField(max_length=5000, blank=True, null=True)
    organizer = models.ForeignKey(User, related_name='organizations', on_delete=models.SET_NULL, null=True)
    moderators = models.ManyToManyField(User, related_name='moderating_organization', blank=True)
    is_approved = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    def clean(self):
        # (No additional field-specific validation required at the moment)
        pass

    class Meta:
        indexes = [
            models.Index(fields=['-created_at'], name='admin_org_created_idx'),
            models.Index(fields=['is_approved', '-created_at'], name='admin_org_approved_idx'),
            models.Index(fields=['organizer', '-created_at'], name='admin_org_organizer_idx'),
        ]
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Hackathon(models.Model):
    title = models.CharField(max_length=100, null=False, blank=False)
    description = models.TextField(null=False, blank=False)
    banner_image = models.URLField(max_length=500, null=True, blank=True)
    venue = models.CharField(max_length=100, default="Default Venue Name")
    details = models.TextField(null=True, blank=True)
    skills = models.ManyToManyField('Skill', related_name='hackathons', blank=True)
    themes = models.ManyToManyField('Theme', related_name='hackathons', blank=True)
    grand_prize = models.IntegerField('grand prize', null=False, default=0)
    start_date = models.DateField(null=False, blank=False)
    visibility = models.BooleanField(default=False, null=False)
    end_date = models.DateField(null=False, blank=False)
    submission_deadline = models.DateTimeField(default=timezone.now() + timedelta(days=7))
    judges = models.ManyToManyField(User, related_name='judged_hackathons', blank=True)
    min_team_size = models.IntegerField('minimum team size', null=False, default=1, validators=[MinValueValidator(1), MaxValueValidator(100)])
    max_team_size = models.IntegerField('maximum team size', null=False, default=5, validators=[MinValueValidator(1), MaxValueValidator(100)])
    organization = models.ForeignKey(Organization, related_name='hackathons', null=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    rules = models.TextField(blank=True, help_text="Enter hackathon rules (one per line or as formatted text)")
    prizes = models.TextField(blank=True, help_text="Enter prize information (one per line or as formatted text)")
    evaluation_criteria = models.TextField(blank=True, help_text="Evaluation criteria for judges (only visible to judges and organizers)")

    def __str__(self):
        return self.title
    
    @property
    def participants(self):
        return self.teams.all()


class Theme(models.Model):
    name = models.CharField(max_length=50, null=False, blank=False)
    description = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class Submission(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('reviewed', 'Reviewed'),
        ('rejected', 'Rejected'),
    ]
    
    project = models.ForeignKey('Project', related_name='submission', on_delete=models.CASCADE, null=True, blank=True)
    hackathon = models.ForeignKey(Hackathon, related_name='submissions', on_delete=models.CASCADE)
    team = models.ForeignKey('Team', related_name='submissions', on_delete=models.CASCADE, null=True, blank=True)
    approved = models.BooleanField(default=False)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['-created_at'], name='admin_sub_created_idx'),
            models.Index(fields=['hackathon', '-created_at'], name='admin_sub_hackathon_idx'),
            models.Index(fields=['team', '-created_at'], name='admin_sub_team_idx'),
            models.Index(fields=['status', '-created_at'], name='admin_sub_status_idx'),
        ]
        ordering = ['-created_at']

    def __str__(self):
        return self.project.title


class Review(models.Model):
    submission = models.ForeignKey(Submission, related_name='reviews', on_delete=models.CASCADE)
    judge = models.ForeignKey(User, related_name='reviews', on_delete=models.CASCADE)
    innovation_score = models.IntegerField(null=False, blank=False, default=0, validators=[MinValueValidator(0), MaxValueValidator(10)])
    technical_score = models.IntegerField(null=False, blank=False, default=0, validators=[MinValueValidator(0), MaxValueValidator(10)])
    user_experience_score = models.IntegerField(null=False, blank=False, default=0, validators=[MinValueValidator(0), MaxValueValidator(10)])
    impact_score = models.IntegerField(null=False, blank=False, default=0, validators=[MinValueValidator(0), MaxValueValidator(10)])
    presentation_score = models.IntegerField(null=False, blank=False, default=0, validators=[MinValueValidator(0), MaxValueValidator(10)])
    overall_score = models.IntegerField(null=False, blank=False, default=0, validators=[MinValueValidator(0), MaxValueValidator(10)])
    review = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['-created_at'], name='admin_rev_created_idx'),
            models.Index(fields=['judge', '-created_at'], name='admin_rev_judge_idx'),
            models.Index(fields=['submission', '-created_at'], name='admin_rev_submission_idx'),
        ]
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.judge.username}'s review for {self.submission.project.title}"


class HackathonParticipant(models.Model):
    hackathon = models.ForeignKey(Hackathon, related_name='individual_participants', on_delete=models.CASCADE)
    user = models.ForeignKey(User, related_name='hackathon_participations', on_delete=models.CASCADE)
    team = models.ForeignKey('Team', related_name='hackathon_participants', on_delete=models.SET_NULL, null=True, blank=True)
    looking_for_team = models.BooleanField(default=True)
    skills_offered = models.ManyToManyField('Skill', related_name='participant_offerings', blank=True)
    bio = models.TextField(max_length=500, blank=True, help_text="Brief bio to help with team matching")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['hackathon', 'user']
        verbose_name = 'Hackathon Participant'
        verbose_name_plural = 'Hackathon Participants'

    def __str__(self):
        return f"{self.user.username} in {self.hackathon.title}"

    @property
    def has_team(self):
        return self.team is not None


class JudgeInvitation(models.Model):
    hackathon = models.ForeignKey(Hackathon, related_name='judge_invitations', on_delete=models.CASCADE)
    email = models.EmailField()
    token = models.CharField(max_length=100, unique=True)
    invited_by = models.ForeignKey(User, related_name='sent_judge_invitations', on_delete=models.CASCADE)
    is_accepted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    accepted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ['hackathon', 'email']
        verbose_name = 'Judge Invitation'
        verbose_name_plural = 'Judge Invitations'

    def save(self, *args, **kwargs):
        if not self.token:
            self.token = secrets.token_urlsafe(32)
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(days=7)  # 7 days to accept
        super().save(*args, **kwargs)

    def is_expired(self):
        return timezone.now() > self.expires_at

    def is_valid(self):
        return not self.is_accepted and not self.is_expired()

    def __str__(self):
        return f"Judge invitation for {self.email} to {self.hackathon.title}"


class Project(models.Model):
    title = models.CharField(max_length=100, null=False, blank=False)
    description = models.TextField(null=False, blank=False)
    github_url = models.URLField("github url", blank=False)
    demo_video_url = models.URLField("Project video link", blank=True)
    live_link = models.URLField("Project live link", blank=True)
    presentation_link = models.URLField("Project presentation link", blank=True)
    team = models.ForeignKey('Team', related_name='projects', null=True, on_delete=models.SET_NULL)
    hackathon = models.ForeignKey(Hackathon, related_name='projects', null=False, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [('team', 'hackathon')]
        indexes = [
            models.Index(fields=['-created_at'], name='admin_proj_created_idx'),
            models.Index(fields=['hackathon', '-created_at'], name='admin_proj_hackathon_idx'),
            models.Index(fields=['team', '-created_at'], name='admin_proj_team_idx'),
        ]
        ordering = ['-created_at']

    def __str__(self):
        return self.title


class ModeratorInvitation(models.Model):
    PENDING = 'pending'
    ACCEPTED = 'accepted'
    DECLINED = 'declined'
    EXPIRED = 'expired'

    STATUS_CHOICES = [
        (PENDING, 'Pending'),
        (ACCEPTED, 'Accepted'),
        (DECLINED, 'Declined'),
        (EXPIRED, 'Expired'),
    ]

    organization = models.ForeignKey(Organization, related_name='moderator_invitations', on_delete=models.CASCADE)
    inviter = models.ForeignKey(User, related_name='sent_moderator_invitations', on_delete=models.CASCADE)
    email = models.EmailField()
    invitee = models.ForeignKey(User, related_name='received_moderator_invitations', on_delete=models.SET_NULL, null=True, blank=True)
    token = models.CharField(max_length=100, unique=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=PENDING)
    message = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    responded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ['organization', 'email']
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        if not self.token:
            self.token = secrets.token_urlsafe(32)
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(days=7)
        super().save(*args, **kwargs)

    def is_expired(self):
        return timezone.now() > self.expires_at

    def is_valid(self):
        return self.status == self.PENDING and not self.is_expired()

    def expire(self):
        if self.is_expired() and self.status == self.PENDING:
            self.status = self.EXPIRED
            self.save()

    def __str__(self):
        return f"Moderator invitation for {self.email} to {self.organization.name}"


class Team(models.Model):
    name = models.CharField(max_length=50, null=False, blank=False)
    members = models.ManyToManyField(User, related_name='teams')
    organizer = models.ForeignKey(User, related_name='organized_teams', null=True, on_delete=models.SET_NULL)
    hackathon = models.ForeignKey(Hackathon, related_name='teams', null=False, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [('name', 'hackathon'), ('organizer', 'hackathon')]
        indexes = [
            models.Index(fields=['-created_at'], name='admin_team_created_idx'),
            models.Index(fields=['hackathon', '-created_at'], name='admin_team_hackathon_idx'),
            models.Index(fields=['organizer', '-created_at'], name='admin_team_organizer_idx'),
        ]
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} - {self.hackathon.title}"
    
    def get_projects(self):
        return self.projects.all()
    
    def get_submissions(self):
        return self.submissions.all()
    
    def get_prizes(self):
        # Return empty queryset since there's no Prize model related to Team
        from django.db.models import QuerySet
        return QuerySet().none()


class TeamInvitation(models.Model):
    team = models.ForeignKey(Team, related_name='invitations', on_delete=models.CASCADE)
    email = models.EmailField()
    invited_by = models.ForeignKey(User, related_name='sent_team_invitations', on_delete=models.CASCADE)
    token = models.CharField(max_length=64, unique=True)
    is_accepted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    accepted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = [('team', 'email')]

    def save(self, *args, **kwargs):
        if not self.token:
            self.token = secrets.token_urlsafe(32)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Invitation to {self.team.name} for {self.email}"


class TeamJoinRequest(models.Model):
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="join_requests")
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    status = models.CharField(max_length=10, choices=[
            ('pending', 'Pending'),
            ('approved', 'Approved'),
            ('rejected', 'Rejected')
        ],
        default='pending'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('team', 'user')


class AuditLog(models.Model):
    admin = models.ForeignKey(User, on_delete=models.CASCADE)
    action = models.CharField(max_length=200)
    target_type = models.CharField(max_length=50, null=True, blank=True)
    target_id = models.CharField(max_length=50, null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)


class PlatformSetting(models.Model):
    key = models.CharField(max_length=100, unique=True)
    value = models.TextField()
    description = models.TextField(blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.key
    
