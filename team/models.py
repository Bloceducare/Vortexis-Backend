from django.db import models

# Create your models here.

class Team(models.Model):
    name = models.CharField(max_length=50, null=False, blank=False)
    members = models.ManyToManyField('accounts.User', related_name='teams')
    organizer = models.ForeignKey('accounts.User', related_name='organized_teams', null=True ,on_delete=models.SET_NULL)
    hackathons = models.ManyToManyField('hackathon.Hackathon', related_name='teams')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name
    
    def get_projects(self):
        return self.projects.all()
    
    def get_submissions(self):
        return self.submissions.all()
    
    def get_prizes(self):
        # Return empty queryset since there's no Prize model related to Team
        from django.db.models import QuerySet
        return QuerySet().none()
    