from django.test import TestCase
from rest_framework.test import APIClient
from django.utils import timezone

from accounts.models import User
from hackathon.models import Hackathon, HackathonParticipant
from team.models import Team
from notifications.models import Notification, EmailNotification


class TeamNotificationsTest(TestCase):
    """Verify notifications are generated when a member leaves a team."""

    def setUp(self):
        # create two users: organizer and member
        self.organizer = User.objects.create_user(
            username='organizer',
            email='org@example.com',
            password='password123'
        )
        self.member = User.objects.create_user(
            username='member',
            email='member@example.com',
            password='password123'
        )

        # create a simple hackathon
        now = timezone.now()
        self.hackathon = Hackathon.objects.create(
            title='Test Hack',
            description='Just a test',
            venue='Online',
            start_date=now.date(),
            end_date=(now + timezone.timedelta(days=1)).date(),
            submission_deadline=now + timezone.timedelta(days=2),
        )

        # add participants
        HackathonParticipant.objects.create(hackathon=self.hackathon, user=self.organizer)
        HackathonParticipant.objects.create(hackathon=self.hackathon, user=self.member)

        # create a team with both users
        self.team = Team.objects.create(
            name='Alpha',
            organizer=self.organizer,
            hackathon=self.hackathon
        )
        self.team.members.set([self.organizer, self.member])

        self.client = APIClient()

    def test_leave_team_triggers_notifications(self):
        # member leaves the team
        self.client.force_authenticate(user=self.member)
        resp = self.client.post(f'/api/v1/team/teams/{self.team.id}/leave_team/')
        self.assertEqual(resp.status_code, 200)
        self.team.refresh_from_db()
        self.assertFalse(self.team.members.filter(id=self.member.id).exists())

        # organizer should have received an in-app notification
        notifs = Notification.objects.filter(user=self.organizer, title__icontains='Member Left Team')
        self.assertTrue(notifs.exists(), "Organizer did not get in-app notification")

        # an email notification record should also have been created
        email_notifs = EmailNotification.objects.filter(user=self.organizer, subject__icontains='Member Left Team')
        self.assertTrue(email_notifs.exists(), "Organizer did not get email notification")

        # member should not receive any notifications about their own departure
        self.assertFalse(Notification.objects.filter(user=self.member).exists())
        self.assertFalse(EmailNotification.objects.filter(user=self.member).exists())

