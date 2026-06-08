from django.core import mail
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from notifications.models import Notification

from .models import Organization, ModeratorInvitation


def make_user(username, email=None, **extra):
    return User.objects.create_user(
        email=email or f'{username}@test.com',
        username=username,
        first_name='Test',
        last_name='User',
        password='testpass123',
        **extra,
    )


def make_org(organizer, name='Test Org', approved=True):
    return Organization.objects.create(
        name=name,
        description='A test organization',
        organizer=organizer,
        is_approved=approved,
    )


INVITE_URL = '/api/v1/organization/invite-moderator/{org_id}/'
ADD_URL = '/api/v1/organization/add-moderator/{org_id}/'
REMOVE_URL = '/api/v1/organization/remove-moderator/{org_id}/'
ACCEPT_URL = '/api/v1/organization/invitation/accept/'
DECLINE_URL = '/api/v1/organization/invitation/decline/'


class ModeratorInvitationTests(APITestCase):
    """Email-based moderator invitation flow (invite-moderator endpoint)."""

    def setUp(self):
        self.organizer = make_user('organizer', is_organizer=True)
        self.org = make_org(self.organizer)
        self.client.force_authenticate(user=self.organizer)

    # --- The core regression: non-registered email must not 500 ---

    def test_invite_unregistered_email_succeeds(self):
        """Inviting an email with no matching User must create the invitation
        and send an email directly (previously 500'd on email_override)."""
        response = self.client.post(
            INVITE_URL.format(org_id=self.org.id),
            {'email': 'newperson@example.com'},
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        invitation = ModeratorInvitation.objects.get(email='newperson@example.com')
        self.assertIsNone(invitation.invitee)
        self.assertEqual(invitation.status, ModeratorInvitation.PENDING)
        self.assertEqual(invitation.organization, self.org)
        # A plain email should have gone out
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('newperson@example.com', mail.outbox[0].to)
        # No in-app notification since there is no user
        self.assertEqual(Notification.objects.count(), 0)

    def test_invite_registered_user_creates_notification_and_links_invitee(self):
        invitee = make_user('moduser')
        response = self.client.post(
            INVITE_URL.format(org_id=self.org.id),
            {'email': invitee.email},
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        invitation = ModeratorInvitation.objects.get(email=invitee.email)
        self.assertEqual(invitation.invitee, invitee)
        # In-app notification created for the registered invitee
        self.assertTrue(Notification.objects.filter(user=invitee).exists())
        # Email also sent
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(invitee.email, mail.outbox[0].to)

    # --- Validation cases (these produce the "enter a valid email" message) ---

    def test_invite_invalid_email_format_returns_400(self):
        response = self.client.post(
            INVITE_URL.format(org_id=self.org.id),
            {'email': 'not-an-email'},
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('email', response.json())

    def test_invite_username_instead_of_email_returns_400(self):
        """Sending a username (no @) into the email field is rejected — this is
        the exact 'enter a valid email address' the frontend was hitting."""
        response = self.client.post(
            INVITE_URL.format(org_id=self.org.id),
            {'email': 'cdev'},
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_invite_existing_moderator_returns_400(self):
        existing = make_user('existingmod')
        self.org.moderators.add(existing)
        response = self.client.post(
            INVITE_URL.format(org_id=self.org.id),
            {'email': existing.email},
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_invite_organizer_self_returns_400(self):
        response = self.client.post(
            INVITE_URL.format(org_id=self.org.id),
            {'email': self.organizer.email},
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_duplicate_pending_invitation_returns_400(self):
        url = INVITE_URL.format(org_id=self.org.id)
        first = self.client.post(url, {'email': 'dupe@example.com'})
        self.assertEqual(first.status_code, status.HTTP_201_CREATED)
        second = self.client.post(url, {'email': 'dupe@example.com'})
        self.assertEqual(second.status_code, status.HTTP_400_BAD_REQUEST)

    # --- Authorization ---

    def test_non_organizer_cannot_invite(self):
        other = make_user('intruder')
        self.client.force_authenticate(user=other)
        response = self.client.post(
            INVITE_URL.format(org_id=self.org.id),
            {'email': 'someone@example.com'},
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_unauthenticated_cannot_invite(self):
        self.client.force_authenticate(user=None)
        response = self.client.post(
            INVITE_URL.format(org_id=self.org.id),
            {'email': 'someone@example.com'},
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_invite_on_missing_organization_is_denied(self):
        # The IsOrganizationOrganizer permission runs before the view body and
        # denies access to a non-existent org (caller is not its organizer),
        # so this is a 403 rather than a 404 — and that's the intended behaviour.
        response = self.client.post(
            INVITE_URL.format(org_id=99999),
            {'email': 'someone@example.com'},
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class InvitationAcceptDeclineTests(APITestCase):
    """Accept / decline flow for moderator invitations."""

    def setUp(self):
        self.organizer = make_user('organizer', is_organizer=True)
        self.org = make_org(self.organizer)
        self.invitee = make_user('invitee')

    def _create_invitation(self, invitee=None, email=None):
        from django.utils import timezone
        from datetime import timedelta
        return ModeratorInvitation.objects.create(
            organization=self.org,
            inviter=self.organizer,
            invitee=invitee,
            email=email or (invitee.email if invitee else 'x@example.com'),
            expires_at=timezone.now() + timedelta(days=7),
        )

    def test_accept_invitation_adds_moderator(self):
        invitation = self._create_invitation(invitee=self.invitee)
        self.client.force_authenticate(user=self.invitee)
        response = self.client.post(ACCEPT_URL, {'token': invitation.token})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        invitation.refresh_from_db()
        self.invitee.refresh_from_db()
        self.assertEqual(invitation.status, ModeratorInvitation.ACCEPTED)
        self.assertIn(self.invitee, self.org.moderators.all())
        self.assertTrue(self.invitee.is_moderator)
        # Inviter gets notified without crashing
        self.assertTrue(Notification.objects.filter(user=self.organizer).exists())

    def test_decline_invitation_sets_status(self):
        invitation = self._create_invitation(invitee=self.invitee)
        self.client.force_authenticate(user=self.invitee)
        response = self.client.post(DECLINE_URL, {'token': invitation.token})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        invitation.refresh_from_db()
        self.assertEqual(invitation.status, ModeratorInvitation.DECLINED)
        self.assertNotIn(self.invitee, self.org.moderators.all())

    def test_accept_with_wrong_user_returns_400(self):
        invitation = self._create_invitation(invitee=self.invitee)
        other = make_user('wronguser')
        self.client.force_authenticate(user=other)
        response = self.client.post(ACCEPT_URL, {'token': invitation.token})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_accept_invalid_token_returns_400(self):
        self.client.force_authenticate(user=self.invitee)
        response = self.client.post(ACCEPT_URL, {'token': 'does-not-exist'})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_unregistered_invite_can_be_accepted_after_signup(self):
        """An email invitation with no invitee can be claimed by whoever
        registers with that email and accepts."""
        invitation = self._create_invitation(email='later@example.com')
        self.assertIsNone(invitation.invitee)
        newcomer = make_user('newcomer', email='later@example.com')
        self.client.force_authenticate(user=newcomer)
        response = self.client.post(ACCEPT_URL, {'token': invitation.token})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        invitation.refresh_from_db()
        self.assertEqual(invitation.invitee, newcomer)
        self.assertIn(newcomer, self.org.moderators.all())


class DirectAddModeratorTests(APITestCase):
    """Username-based direct add/remove (add-moderator endpoint)."""

    def setUp(self):
        self.organizer = make_user('organizer', is_organizer=True)
        self.org = make_org(self.organizer)
        self.mod = make_user('directmod')
        self.client.force_authenticate(user=self.organizer)

    def test_organizer_adds_moderator_by_username(self):
        response = self.client.post(
            ADD_URL.format(org_id=self.org.id),
            {'moderators': [self.mod.username]},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn(self.mod, self.org.moderators.all())

    def test_add_nonexistent_username_returns_400(self):
        response = self.client.post(
            ADD_URL.format(org_id=self.org.id),
            {'moderators': ['ghost']},
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_non_organizer_cannot_add_moderator(self):
        other = make_user('intruder')
        self.client.force_authenticate(user=other)
        response = self.client.post(
            ADD_URL.format(org_id=self.org.id),
            {'moderators': [self.mod.username]},
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_organizer_removes_moderator_by_username(self):
        self.org.moderators.add(self.mod)
        response = self.client.post(
            REMOVE_URL.format(org_id=self.org.id),
            {'moderators': [self.mod.username]},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertNotIn(self.mod, self.org.moderators.all())
