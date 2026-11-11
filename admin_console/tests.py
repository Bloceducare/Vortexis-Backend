import datetime
from unittest.mock import MagicMock, patch

from io import StringIO

from django.core import mail
from django.core.cache import cache
from django.core.management import call_command
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from admin_console.models import AuditLog
from admin_console.views import clear_public_page_cache
from hackathon.models import Hackathon, Submission
from organization.models import Organization
from project.models import Project
from team.models import Team

CONSOLE = '/api/v1/console'
PUBLIC_HACKATHONS = '/api/v1/hackathon/'


def make_user(username, **extra):
    return User.objects.create_user(
        email=f'{username}@example.com', username=username,
        first_name=username.title(), last_name='Tester', password='pw12345', **extra,
    )


class ConsoleBase(APITestCase):
    def setUp(self):
        # Rate limits are not under test and their counters can persist in Redis.
        patcher = patch('rest_framework.throttling.SimpleRateThrottle.allow_request', return_value=True)
        patcher.start()
        self.addCleanup(patcher.stop)

        self.admin = make_user('admin', is_admin=True, is_verified=True)
        self.owner = make_user('owner', is_verified=True)
        self.org = Organization.objects.create(name='Acme Org', description='d', organizer=self.owner)
        self.client.force_authenticate(self.admin)
        # The public list is cached; start every test from a clean page cache.
        clear_public_page_cache()
        self.addCleanup(clear_public_page_cache)

    def make_hackathon(self, title='Hack One', visibility=False, start_offset=2, length=3, org=None):
        today = timezone.now().date()
        return Hackathon.objects.create(
            title=title, description='d', venue='Online',
            start_date=today + datetime.timedelta(days=start_offset),
            end_date=today + datetime.timedelta(days=start_offset + length),
            submission_deadline=timezone.now() + datetime.timedelta(days=start_offset + length),
            rules='r', prizes='p', evaluation_criteria='e',
            organization=org or self.org, visibility=visibility,
        )

    def public_ids(self):
        body = self.client.get(PUBLIC_HACKATHONS).json()
        rows = body
        if isinstance(body, dict):
            rows = body.get('results') or body.get('data') or []
        return {row['id'] for row in rows}

    def audit_actions(self):
        return list(AuditLog.objects.order_by('id').values_list('action', 'admin_id'))


class HackathonActionTests(ConsoleBase):
    """approve/reject/suspend/restore used to assign non-existent model fields and
    returned 200 without saving anything. They must change `visibility`, the field
    the public listing actually filters on."""

    def test_approve_persists_and_publishes(self):
        h = self.make_hackathon(visibility=False)
        self.assertNotIn(h.id, self.public_ids())

        r = self.client.patch(f'{CONSOLE}/hackathons/{h.id}/approve/')

        self.assertEqual(r.status_code, status.HTTP_200_OK, r.content)
        self.assertTrue(r.json()['visibility'])
        h.refresh_from_db()
        self.assertTrue(h.visibility)
        self.assertIn(h.id, self.public_ids())

    def test_suspend_persists_and_hides_from_public(self):
        h = self.make_hackathon(visibility=True)
        self.assertIn(h.id, self.public_ids())

        r = self.client.patch(f'{CONSOLE}/hackathons/{h.id}/suspend/')

        self.assertEqual(r.status_code, status.HTTP_200_OK)
        h.refresh_from_db()
        self.assertFalse(h.visibility)
        self.assertNotIn(h.id, self.public_ids())

    def test_restore_makes_it_public_again(self):
        h = self.make_hackathon(visibility=True)
        self.client.patch(f'{CONSOLE}/hackathons/{h.id}/suspend/')
        self.assertNotIn(h.id, self.public_ids())

        self.client.patch(f'{CONSOLE}/hackathons/{h.id}/restore/')

        h.refresh_from_db()
        self.assertTrue(h.visibility)
        self.assertIn(h.id, self.public_ids())

    def test_clearing_the_page_cache_leaves_other_cache_entries_alone(self):
        """The cache also holds OTPs and throttle counters; only cached pages may be removed."""
        cache.set('otp:test-user', '123456', 300)
        h = self.make_hackathon(visibility=True)
        self.public_ids()  # populate the cached public list
        self.client.patch(f'{CONSOLE}/hackathons/{h.id}/suspend/')
        self.assertEqual(cache.get('otp:test-user'), '123456')
        self.assertNotIn(h.id, self.public_ids())

    def test_a_cache_failure_does_not_fail_the_action(self):
        h = self.make_hackathon(visibility=False)
        broken_cache = MagicMock()
        broken_cache.delete_pattern.side_effect = RuntimeError('cache is down')
        with patch('admin_console.views.cache', broken_cache):
            r = self.client.patch(f'{CONSOLE}/hackathons/{h.id}/approve/')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        h.refresh_from_db()
        self.assertTrue(h.visibility)

    def test_reject_hides_it(self):
        h = self.make_hackathon(visibility=True)

        r = self.client.patch(f'{CONSOLE}/hackathons/{h.id}/reject/')

        self.assertEqual(r.status_code, status.HTTP_200_OK)
        h.refresh_from_db()
        self.assertFalse(h.visibility)

    def test_actions_only_touch_visibility(self):
        h = self.make_hackathon(title='Keep Me', visibility=False)
        self.client.patch(f'{CONSOLE}/hackathons/{h.id}/approve/')
        h.refresh_from_db()
        self.assertEqual((h.title, h.venue, h.description), ('Keep Me', 'Online', 'd'))

    def test_every_action_is_audited_with_the_acting_admin(self):
        h = self.make_hackathon()
        for action in ('approve', 'suspend', 'restore', 'reject'):
            self.client.patch(f'{CONSOLE}/hackathons/{h.id}/{action}/')
        self.assertEqual(self.audit_actions(), [
            ('APPROVE_HACKATHON', self.admin.id), ('SUSPEND_HACKATHON', self.admin.id),
            ('RESTORE_HACKATHON', self.admin.id), ('REJECT_HACKATHON', self.admin.id),
        ])

    def test_unknown_hackathon_is_404(self):
        self.assertEqual(self.client.patch(f'{CONSOLE}/hackathons/99999/approve/').status_code, 404)

    def test_non_admin_cannot_use_actions(self):
        h = self.make_hackathon(visibility=False)
        self.client.force_authenticate(make_user('plain', is_verified=True))
        r = self.client.patch(f'{CONSOLE}/hackathons/{h.id}/approve/')
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)
        h.refresh_from_db()
        self.assertFalse(h.visibility)

    def test_anonymous_cannot_use_actions(self):
        h = self.make_hackathon()
        self.client.force_authenticate(None)
        self.assertEqual(self.client.patch(f'{CONSOLE}/hackathons/{h.id}/approve/').status_code, 401)


class OrganizationActionTests(ConsoleBase):
    def test_approve_grants_organizer_role_and_notifies(self):
        """Approving only flipped is_approved, so the organizer still failed the
        `user.is_organizer` check when creating a hackathon."""
        self.assertFalse(self.owner.is_organizer)

        r = self.client.patch(f'{CONSOLE}/organizations/{self.org.id}/approve/')

        self.assertEqual(r.status_code, status.HTTP_200_OK, r.content)
        self.org.refresh_from_db()
        self.owner.refresh_from_db()
        self.assertTrue(self.org.is_approved)
        self.assertTrue(self.owner.is_organizer)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [self.owner.email])

    def test_approve_matches_the_platforms_own_approve_endpoint(self):
        other_org = Organization.objects.create(name='Other Org', description='d', organizer=make_user('other', is_verified=True))
        self.client.post(f'/api/v1/organization/approve/{other_org.id}/')
        other_org.refresh_from_db()
        other_org.organizer.refresh_from_db()
        self.client.patch(f'{CONSOLE}/organizations/{self.org.id}/approve/')
        self.org.refresh_from_db()
        self.owner.refresh_from_db()
        self.assertEqual(
            (other_org.is_approved, other_org.organizer.is_organizer),
            (self.org.is_approved, self.owner.is_organizer),
        )

    def test_organizer_can_create_hackathons_only_after_admin_approves_the_org(self):
        """The real-world symptom: an organizer whose org was approved in the admin
        console still got 'Your account does not have organizer permissions'."""
        create = '/api/v1/hackathon/create/'
        self.client.force_authenticate(self.owner)
        before = self.client.post(create, {'title': 'My Hack'}, format='json')
        self.assertEqual(before.status_code, status.HTTP_403_FORBIDDEN)  # blocked at the permission gate

        self.client.force_authenticate(self.admin)
        self.client.patch(f'{CONSOLE}/organizations/{self.org.id}/approve/')

        self.owner.refresh_from_db()  # a real request loads the user from the DB via its JWT
        self.client.force_authenticate(self.owner)
        after = self.client.post(create, {'title': 'My Hack'}, format='json')
        # Past the permission gate: the incomplete payload now fails validation (400), not permissions (403).
        self.assertEqual(after.status_code, status.HTTP_400_BAD_REQUEST, after.content[:300])

    def test_approve_without_an_organizer_does_not_crash(self):
        orphan = Organization.objects.create(name='Orphan', description='d', organizer=self.owner)
        Organization.objects.filter(pk=orphan.pk).update(organizer=None)  # e.g. the organizer's account was deleted
        r = self.client.patch(f'{CONSOLE}/organizations/{orphan.id}/approve/')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        orphan.refresh_from_db()
        self.assertTrue(orphan.is_approved)

    def test_reject_unapproves_but_keeps_organizer_role(self):
        self.client.patch(f'{CONSOLE}/organizations/{self.org.id}/approve/')
        self.client.patch(f'{CONSOLE}/organizations/{self.org.id}/reject/')
        self.org.refresh_from_db()
        self.owner.refresh_from_db()
        self.assertFalse(self.org.is_approved)
        self.assertTrue(self.owner.is_organizer)  # may organise through another org

    def test_suspend_and_restore_persist(self):
        """These used to assign `is_suspended`, which the model does not have."""
        self.client.patch(f'{CONSOLE}/organizations/{self.org.id}/approve/')

        r = self.client.patch(f'{CONSOLE}/organizations/{self.org.id}/suspend/')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.org.refresh_from_db()
        self.assertFalse(self.org.is_approved)

        r = self.client.patch(f'{CONSOLE}/organizations/{self.org.id}/restore/')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.org.refresh_from_db()
        self.assertTrue(self.org.is_approved)

    def test_actions_are_audited(self):
        for action in ('approve', 'suspend', 'restore', 'reject'):
            self.client.patch(f'{CONSOLE}/organizations/{self.org.id}/{action}/')
        self.assertEqual([a for a, _ in self.audit_actions()], [
            'APPROVE_ORGANIZATION', 'SUSPEND_ORGANIZATION', 'RESTORE_ORGANIZATION', 'REJECT_ORGANIZATION',
        ])

    def test_non_admin_cannot_approve(self):
        self.client.force_authenticate(self.owner)
        r = self.client.patch(f'{CONSOLE}/organizations/{self.org.id}/approve/')
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)
        self.org.refresh_from_db()
        self.assertFalse(self.org.is_approved)


class ListFilterTests(ConsoleBase):
    """These query-string filters referenced fields that do not exist and raised
    FieldError (HTTP 500) as soon as a client used them."""

    def ids(self, path):
        r = self.client.get(f'{CONSOLE}{path}')
        self.assertEqual(r.status_code, status.HTTP_200_OK, f'{path}: {r.content[:200]}')
        return {row['id'] for row in r.json()}

    def test_hackathon_status_filter_uses_dates(self):
        upcoming = self.make_hackathon('Up', start_offset=5)
        ongoing = self.make_hackathon('On', start_offset=-1, length=4)
        done = self.make_hackathon('Done', start_offset=-10, length=2)
        self.assertEqual(self.ids('/hackathons/?status=upcoming'), {upcoming.id})
        self.assertEqual(self.ids('/hackathons/?status=ongoing'), {ongoing.id})
        self.assertEqual(self.ids('/hackathons/?status=completed'), {done.id})

    def test_hackathon_visibility_filters(self):
        shown = self.make_hackathon('Shown', visibility=True)
        hidden = self.make_hackathon('Hidden', visibility=False)
        self.assertEqual(self.ids('/hackathons/?visibility=true'), {shown.id})
        self.assertEqual(self.ids('/hackathons/?visibility=false'), {hidden.id})
        self.assertEqual(self.ids('/hackathons/?is_approved=true'), {shown.id})
        self.assertEqual(self.ids('/hackathons/?is_suspended=true'), {hidden.id})
        self.assertEqual(self.ids('/hackathons/?is_suspended=false'), {shown.id})

    def test_submissions_user_filter_uses_team_membership(self):
        h = self.make_hackathon()
        member = make_user('member', is_verified=True)
        team = Team.objects.create(name='T', hackathon=h)
        team.members.add(member)
        project = Project.objects.create(title='P', description='d', github_url='https://github.com/x/y', hackathon=h, team=team)
        sub = Submission.objects.create(project=project, hackathon=h, team=team)
        self.assertEqual(self.ids(f'/submissions/?user_id={member.id}'), {sub.id})
        self.assertEqual(self.ids(f'/submissions/?user_id={self.admin.id}'), set())

    def test_organization_filters(self):
        approved = Organization.objects.create(name='Yes Org', description='d', organizer=self.owner, is_approved=True)
        self.assertEqual(self.ids('/organizations/?is_approved=true'), {approved.id})
        self.assertEqual(self.ids('/organizations/?is_approved=false'), {self.org.id})
        self.assertEqual(self.ids('/organizations/?name=yes'), {approved.id})
        # unsupported params are ignored rather than crashing
        self.assertEqual(self.ids('/organizations/?is_active=true&is_suspended=true'), {approved.id, self.org.id})

    def test_settings_filter(self):
        self.client.post(f'{CONSOLE}/settings/', {'key': 'support_email', 'value': 'a@b.c'})
        self.assertEqual(len(self.ids('/settings/?key=support')), 1)
        self.assertEqual(self.ids('/settings/?is_active=true'), self.ids('/settings/'))


class FixOrganizerRolesCommandTests(ConsoleBase):
    """Repairs organizations that were approved before approval granted the role."""

    def run_command(self, *args):
        out = StringIO()
        call_command('fix_organizer_roles', *args, stdout=out)
        return out.getvalue()

    def stranded_org(self, name, approved=True):
        user = make_user(f'org_{name}', is_verified=True)
        Organization.objects.create(name=name, description='d', organizer=user, is_approved=approved)
        return user

    def test_dry_run_reports_but_changes_nothing(self):
        stranded = self.stranded_org('a')
        out = self.run_command()
        stranded.refresh_from_db()
        self.assertFalse(stranded.is_organizer)
        self.assertIn('Dry run', out)
        self.assertIn(f'user #{stranded.id}', out)

    def test_apply_grants_the_role_to_approved_organizers_only(self):
        approved = self.stranded_org('approved')
        pending = self.stranded_org('pending', approved=False)
        out = self.run_command('--apply')
        approved.refresh_from_db()
        pending.refresh_from_db()
        self.assertTrue(approved.is_organizer)
        self.assertFalse(pending.is_organizer)  # unapproved orgs must not get the role
        self.assertIn('Granted the organizer role to', out)

    def test_it_is_idempotent_and_leaves_other_users_alone(self):
        self.stranded_org('a')
        bystander = make_user('bystander', is_verified=True)
        self.run_command('--apply')
        out = self.run_command('--apply')
        bystander.refresh_from_db()
        self.assertFalse(bystander.is_organizer)
        self.assertIn('Nothing to fix', out)

    def test_repaired_organizer_passes_the_hackathon_creation_gate(self):
        stranded = self.stranded_org('gate')
        self.client.force_authenticate(stranded)
        before = self.client.post('/api/v1/hackathon/create/', {'title': 'X'}, format='json')
        self.assertEqual(before.status_code, status.HTTP_403_FORBIDDEN)

        self.run_command('--apply')
        stranded.refresh_from_db()
        self.client.force_authenticate(stranded)
        after = self.client.post('/api/v1/hackathon/create/', {'title': 'X'}, format='json')
        self.assertEqual(after.status_code, status.HTTP_400_BAD_REQUEST)  # past the gate; payload incomplete
