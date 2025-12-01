from django.db import models
from django.utils import timezone
from django.core.validators import URLValidator
from datetime import timedelta
import secrets
import re

class Organization(models.Model):
    name = models.CharField(max_length=128, unique=True)
    description = models.TextField()
    website = models.URLField(max_length=200, blank=True, null=True, validators=[URLValidator()])
    logo = models.URLField(max_length=500, blank=True, null=True)
    custom_url = models.CharField(max_length=128, unique=True, blank=True, null=True)
    location = models.CharField(max_length=32, blank=True, null=True)
    tagline = models.CharField(max_length=200, blank=True, null=True)
    about = models.TextField(max_length=5000, blank=True, null=True)
    organizer = models.ForeignKey('accounts.User', related_name='organizations', on_delete=models.SET_NULL, null=True)
    moderators = models.ManyToManyField('accounts.User', related_name='moderating_organization', blank=True)
    is_approved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def clean(self):
        # Validate custom_url format if provided
        if self.custom_url:
            if not re.match(r'^[a-zA-Z0-9_-]+$', self.custom_url):
                raise models.ValidationError({
                    'custom_url': 'Custom URL can only contain letters, numbers, hyphens, and underscores.'
                })

    class Meta:
        indexes = [
            models.Index(fields=['-created_at'], name='org_created_idx'),
            models.Index(fields=['is_approved', '-created_at'], name='org_approved_idx'),
            models.Index(fields=['organizer', '-created_at'], name='org_organizer_idx'),
        ]
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


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
    inviter = models.ForeignKey('accounts.User', related_name='sent_moderator_invitations', on_delete=models.CASCADE)
    email = models.EmailField()
    invitee = models.ForeignKey('accounts.User', related_name='received_moderator_invitations', on_delete=models.SET_NULL, null=True, blank=True)
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
