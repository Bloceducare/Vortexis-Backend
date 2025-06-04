from django.db import models

class Organization(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField()
    organizer = models.OneToOneField('accounts.User', related_name='organization', on_delete=models.SET_NULL, null=True)
    moderators = models.ManyToManyField('accounts.User', related_name='moderating_organization', blank=True)
    is_approved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name
