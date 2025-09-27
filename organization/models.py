from django.db import models
from django.utils import timezone
from datetime import timedelta
import secrets

class Organization(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField()
    organizer = models.ForeignKey('accounts.User', related_name='organizations', on_delete=models.SET_NULL, null=True)
    moderators = models.ManyToManyField('accounts.User', related_name='moderating_organization', blank=True)
    is_approved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

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
