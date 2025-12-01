from django.db import models
from team.models import Team

class Project(models.Model):
    title = models.CharField(max_length=100, null=False, blank=False)
    description = models.TextField(null=False, blank=False)
    github_url = models.URLField("github url", blank=False)
    demo_video_url = models.URLField("Project video link", blank=True)
    live_link = models.URLField("Project live link", blank=True)
    presentation_link = models.URLField("Project presentation link", blank=True)
    team = models.ForeignKey(Team, related_name='projects', null=True, on_delete=models.SET_NULL)
    hackathon = models.ForeignKey('hackathon.Hackathon', related_name='projects', null=False, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [('team', 'hackathon')]
        indexes = [
            models.Index(fields=['-created_at'], name='proj_created_idx'),
            models.Index(fields=['hackathon', '-created_at'], name='proj_hackathon_idx'),
            models.Index(fields=['team', '-created_at'], name='proj_team_idx'),
        ]
        ordering = ['-created_at']

    def __str__(self):
        return self.title
