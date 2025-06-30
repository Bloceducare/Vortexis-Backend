from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator

# Create your models here.
class Hackathon(models.Model):
    title = models.CharField(max_length=100, null=False, blank=False)
    description = models.TextField(null=False, blank=False)
    banner_image = models.ImageField(upload_to='hackathon_banners/', null=True, blank=True)
    venue = models.CharField(max_length=100, null=False, blank=False)
    details = models.TextField(null=True, blank=True)
    skills = models.ManyToManyField('accounts.Skill', related_name='hackathons', blank=True)
    themes = models.ManyToManyField('Theme', related_name='hackathons', blank=True)
    grand_prize = models.IntegerField('grand prize', null=False, default=0)
    start_date = models.DateField(null=False, blank=False)
    visibility = models.BooleanField(default=False, null=False)
    end_date = models.DateField(null=False, blank=False)
    judges = models.ManyToManyField('accounts.User', related_name='judged_hackathons', blank=True)
    min_team_size = models.IntegerField('minimum team size', null=False, default=1, validators=[MinValueValidator(1), MaxValueValidator(100)])
    max_team_size = models.IntegerField('maximum team size', null=False, default=5, validators=[MinValueValidator(1), MaxValueValidator(100)])
    organization = models.ForeignKey('organization.Organization', related_name='hackathons', null=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    rules = models.JSONField(default=list, blank=True)
    prizes = models.JSONField(default=list, blank=True)

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
    project = models.OneToOneField('project.Project', related_name='submission', on_delete=models.CASCADE)
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

