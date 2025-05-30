# Generated by Django 5.1.6 on 2025-03-10 10:17

from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('hackathon', '0002_alter_hackathon_organization'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Team',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=50)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('hackathons', models.ManyToManyField(related_name='teams', to='hackathon.hackathon')),
                ('members', models.ManyToManyField(related_name='teams', to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]
