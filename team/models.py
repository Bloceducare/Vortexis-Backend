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
    
    @property
    def projects(self):
        return self.projects.all()
    
    @property
    def submissions(self):
        return self.submissions.all()
    
    @property
    def prizes(self):
        return self.prizes.all()
    