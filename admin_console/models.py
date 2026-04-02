from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
import secrets
from accounts.models import User
from hackathon.models import Hackathon, Submission, Theme
from organization.models import Organization
from team.models import Team
from project.models import Project


# Admin-specific Review model for submission scoring
class Review(models.Model):
    submission = models.ForeignKey(Submission, related_name='admin_reviews', on_delete=models.CASCADE)
    judge = models.ForeignKey(User, related_name='admin_reviews', on_delete=models.CASCADE)
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


# Audit log model for tracking admin actions
class AuditLog(models.Model):
    admin = models.ForeignKey(User, on_delete=models.CASCADE)
    action = models.CharField(max_length=200)
    target_type = models.CharField(max_length=50, null=True, blank=True)
    target_id = models.CharField(max_length=50, null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)


# Platform-wide settings for admins
class PlatformSetting(models.Model):
    key = models.CharField(max_length=100, unique=True)
    value = models.TextField()
    description = models.TextField(blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.key
    
