from django.db import models
from django.utils import timezone


class Conversation(models.Model):
    TYPE_CHOICES = [
        ('dm', 'Direct Message'),
        ('team', 'Team'),
        ('judges', 'Judges'),
    ]

    type = models.CharField(max_length=16, choices=TYPE_CHOICES)
    # Optional scoping to entities
    team = models.ForeignKey('team.Team', related_name='conversations', null=True, blank=True, on_delete=models.CASCADE)
    hackathon = models.ForeignKey('hackathon.Hackathon', related_name='conversations', null=True, blank=True, on_delete=models.CASCADE)
    organization = models.ForeignKey('organization.Organization', related_name='conversations', null=True, blank=True, on_delete=models.SET_NULL)
    title = models.CharField(max_length=200, blank=True, default='')
    created_by = models.ForeignKey('accounts.User', related_name='created_conversations', on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['type']),
        ]

    def __str__(self) -> str:
        if self.type == 'dm':
            return self.title or f"DM #{self.id}"
        if self.type == 'team' and self.team:
            return f"Team: {self.team.name}"
        if self.type == 'judges' and self.hackathon:
            return f"Judges: {self.hackathon.title}"
        return self.title or f"Conversation #{self.id}"


class ConversationParticipant(models.Model):
    conversation = models.ForeignKey(Conversation, related_name='participants', on_delete=models.CASCADE)
    user = models.ForeignKey('accounts.User', related_name='conversations', on_delete=models.CASCADE)
    is_admin = models.BooleanField(default=False)
    can_post = models.BooleanField(default=True)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [('conversation', 'user')]
        indexes = [
            models.Index(fields=['conversation', 'user']),
        ]

    def __str__(self) -> str:
        return f"{self.user.username} in {self.conversation}"


class Message(models.Model):
    conversation = models.ForeignKey(Conversation, related_name='messages', on_delete=models.CASCADE)
    sender = models.ForeignKey('accounts.User', related_name='sent_messages', on_delete=models.CASCADE)
    content = models.TextField(blank=False)
    created_at = models.DateTimeField(auto_now_add=True)
    edited_at = models.DateTimeField(null=True, blank=True)
    is_deleted = models.BooleanField(default=False)

    class Meta:
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['conversation', 'created_at']),
            models.Index(fields=['sender']),
            models.Index(fields=['conversation', '-created_at']),
        ]

    def __str__(self) -> str:
        return f"Message from {self.sender.username} in {self.conversation}"

    def clean(self):
        from django.core.exceptions import ValidationError
        if not self.content or not self.content.strip():
            raise ValidationError("Message content cannot be empty")

    def edit(self, new_content: str):
        if not new_content or not new_content.strip():
            from django.core.exceptions import ValidationError
            raise ValidationError("Message content cannot be empty")
        self.content = new_content
        self.edited_at = timezone.now()
        self.save(update_fields=['content', 'edited_at'])

    def soft_delete(self):
        self.is_deleted = True
        self.save(update_fields=['is_deleted'])

