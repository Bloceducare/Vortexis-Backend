from django.db import models

# Create your models here.
class Organization(models.Model):
    name = models.CharField(max_length=50, null=False, blank=False)
    description = models.TextField(null=False, blank=False)
    organizer = models.OneToOneField('accounts.User', related_name='organization', blank=True, null=True, on_delete=models.SET_NULL)
    moderators = models.ManyToManyField('accounts.User', related_name='moderating_organization', blank=True)
    is_approved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name