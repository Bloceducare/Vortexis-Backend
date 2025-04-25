from django.db import models
from team.models import Team

class Project(models.Model):
    title = models.CharField(max_length=100, null=False, blank=False)
    description = models.TextField(null=False, blank=False)
    github_url = models.URLField("github url", blank=False)
    live_link = models.URLField("Project live link", blank=True)
    team = models.ForeignKey(Team, related_name='projects', null=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title
