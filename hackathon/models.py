from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from datetime import timedelta
import secrets

# Create your models here.
class Hackathon(models.Model):
    title = models.CharField(max_length=100, null=False, blank=False)
    description = models.TextField(null=False, blank=False)
    banner_image = models.URLField(max_length=500, null=True, blank=True)
    venue = models.CharField(max_length=100, null=False, blank=False)
    details = models.TextField(null=True, blank=True)
    skills = models.ManyToManyField('accounts.Skill', related_name='hackathons', blank=True)
    themes = models.ManyToManyField('Theme', related_name='hackathons', blank=True)
    grand_prize = models.IntegerField('grand prize', null=False, default=0)
    start_date = models.DateField(null=False, blank=False)
    visibility = models.BooleanField(default=False, null=False)
    end_date = models.DateField(null=False, blank=False)
    submission_deadline = models.DateTimeField(null=False, blank=False)
    judges = models.ManyToManyField('accounts.User', related_name='judged_hackathons', blank=True)
    min_team_size = models.IntegerField('minimum team size', null=False, default=1, validators=[MinValueValidator(1), MaxValueValidator(100)])
    max_team_size = models.IntegerField('maximum team size', null=False, default=5, validators=[MinValueValidator(1), MaxValueValidator(100)])
    organization = models.ForeignKey('organization.Organization', related_name='hackathons', null=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)
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
    
    project = models.OneToOneField('project.Project', related_name='submission', on_delete=models.CASCADE)
    hackathon = models.ForeignKey(Hackathon, related_name='submissions', on_delete=models.CASCADE)
    team = models.ForeignKey('team.Team', related_name='submissions', on_delete=models.CASCADE)
    approved = models.BooleanField(default=False)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.project.title

class Review(models.Model):
    submission = models.ForeignKey(Submission, related_name='reviews', on_delete=models.CASCADE)
    judge = models.ForeignKey('accounts.User', related_name='reviews', on_delete=models.CASCADE)
    innovation_score = models.IntegerField(null=False, blank=False, default=0, validators=[MinValueValidator(0), MaxValueValidator(10)])
    technical_score = models.IntegerField(null=False, blank=False, default=0, validators=[MinValueValidator(0), MaxValueValidator(10)])
    user_experience_score = models.IntegerField(null=False, blank=False, default=0, validators=[MinValueValidator(0), MaxValueValidator(10)])
    impact_score = models.IntegerField(null=False, blank=False, default=0, validators=[MinValueValidator(0), MaxValueValidator(10)])
    presentation_score = models.IntegerField(null=False, blank=False, default=0, validators=[MinValueValidator(0), MaxValueValidator(10)])
    overall_score = models.IntegerField(null=False, blank=False, default=0, validators=[MinValueValidator(0), MaxValueValidator(10)])
    review = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.judge.username}'s review for {self.submission.project.title}"

class HackathonParticipant(models.Model):
    hackathon = models.ForeignKey(Hackathon, related_name='individual_participants', on_delete=models.CASCADE)
    user = models.ForeignKey('accounts.User', related_name='hackathon_participations', on_delete=models.CASCADE)
    team = models.ForeignKey('team.Team', related_name='hackathon_participants', on_delete=models.SET_NULL, null=True, blank=True)
    looking_for_team = models.BooleanField(default=True)
    skills_offered = models.ManyToManyField('accounts.Skill', related_name='participant_offerings', blank=True)
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
    invited_by = models.ForeignKey('accounts.User', related_name='sent_judge_invitations', on_delete=models.CASCADE)
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

