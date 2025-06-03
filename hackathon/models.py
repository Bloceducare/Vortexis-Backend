from django.db import models
from project.models import Project
from django.core.validators import MinValueValidator, MaxValueValidator

# Create your models here.
class Hackathon(models.Model):
    title = models.CharField(max_length=100, null=False, blank=False)
    description = models.TextField(null=False, blank=False)
    venue = models.CharField(max_length=100, null=False, blank=False)
    details = models.TextField(null=True, blank=True)
    skills = models.ManyToManyField('accounts.Skill', related_name='hackathons', blank=True)
    themes = models.ManyToManyField('Theme', related_name='hackathons', blank=True)
    grand_prize = models.IntegerField('grand prize', null=False, default=0)
    start_date = models.DateField(null=False, blank=False)
    visibility = models.BooleanField(default=False, null=False)
    end_date = models.DateField(null=False, blank=False)
    judges = models.ManyToManyField('accounts.User', related_name='hackathons_as_judge', blank=True)
    min_team_size = models.IntegerField('minimum team size', null=False, default=1, validators=[MinValueValidator(1), MaxValueValidator(100)])
    max_team_size = models.IntegerField('maximum team size', null=False, default=5, validators=[MinValueValidator(1), MaxValueValidator(100)])
    organization = models.ForeignKey('organization.Organization', related_name='hackathons', null=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title
    
    @property
    def participants(self):
        return self.teams.all()
    
    @property
    def themes(self):
        return self.themes.all()
    
    @property
    def rules(self):
        return self.rules.all()
    
    @property
    def prizes(self):
        return self.prizes.all()
    
    @property
    def submissions(self):
        return self.submissions.all()

class Theme(models.Model):
    name = models.CharField(max_length=50, null=False, blank=False)
    description = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

class Rule(models.Model):
    description = models.TextField(null=False, blank=False)
    hackathon = models.ForeignKey(Hackathon, related_name='rules', on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.description

class Submission(models.Model):
    project = models.OneToOneField(Project, related_name='submission', on_delete=models.CASCADE)
    hackathon = models.ForeignKey(Hackathon, related_name='submissions', on_delete=models.CASCADE)
    team = models.ForeignKey('team.Team', related_name='submissions', on_delete=models.CASCADE)
    approved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.project.title

class Review(models.Model):
    submission = models.ForeignKey(Submission, related_name='reviews', on_delete=models.CASCADE)
    judge = models.ForeignKey('accounts.User', related_name='reviews', on_delete=models.CASCADE)
    score = models.IntegerField(null=False, blank=False)
    review = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.judge.username}'s review for {self.submission.project.title}"

class Prize(models.Model):
    name = models.CharField(max_length=50, null=False, blank=False)
    amount = models.IntegerField('prize amount', null=False)
    hackathon = models.ForeignKey(Hackathon, on_delete=models.CASCADE, related_name='prizes', blank=False)
    recipient = models.ForeignKey('team.Team', related_name='prizes', blank=True, null=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

