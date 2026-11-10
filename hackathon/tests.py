from datetime import date, timedelta

from django.core.cache import cache
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from organization.models import Organization

from .models import Hackathon

LIST_URL = '/api/v1/hackathon/'


def make_user(n=1):
    return User.objects.create_user(
        email=f'user{n}@test.com',
        username=f'user{n}',
        first_name='Test',
        last_name='User',
        password='testpass123',
    )


def make_org(organizer):
    return Organization.objects.create(
        name='Test Org',
        description='A test organization',
        organizer=organizer,
        is_approved=True,
    )


def make_hackathon(org, title='Hackathon', active=True, visible=True, offset_days=0):
    today = date.today()
    future = today + timedelta(days=30)
    past_end = today - timedelta(days=1)
    deadline = timezone.now() + timedelta(days=30)

    end = future if active else past_end
    return Hackathon.objects.create(
        title=title,
        description='Test description',
        venue='Online',
        visibility=visible,
        start_date=today - timedelta(days=offset_days),
        end_date=end,
        submission_deadline=deadline if active else timezone.now() - timedelta(days=1),
        organization=org,
        grand_prize=1000,
    )


class HackathonListPaginationTests(APITestCase):

    def setUp(self):
        cache.clear()
        self.organizer = make_user(1)
        self.org = make_org(self.organizer)
        today = date.today()
        future = today + timedelta(days=30)
        deadline = timezone.now() + timedelta(days=30)

        # 12 active visible hackathons — created in order so created_at is ascending
        for i in range(12):
            Hackathon.objects.create(
                title=f'Active Hackathon {i + 1:02d}',
                description='Test',
                venue='Online',
                visibility=True,
                start_date=today,
                end_date=future,
                submission_deadline=deadline,
                organization=self.org,
            )

        # Ended hackathon — should be excluded from active list
        Hackathon.objects.create(
            title='Ended Hackathon',
            description='Test',
            venue='Online',
            visibility=True,
            start_date=today - timedelta(days=10),
            end_date=today - timedelta(days=1),
            submission_deadline=timezone.now() - timedelta(days=1),
            organization=self.org,
        )

        # Private hackathon — should be excluded
        Hackathon.objects.create(
            title='Private Hackathon',
            description='Test',
            venue='Online',
            visibility=False,
            start_date=today,
            end_date=future,
            submission_deadline=deadline,
            organization=self.org,
        )

    # --- Default pagination ---

    def test_default_returns_paginated_response_shape(self):
        response = self.client.get(LIST_URL)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        body = response.json()
        self.assertIn('data', body)
        self.assertIn('pagination', body)
        pagination = body['pagination']
        self.assertIn('page', pagination)
        self.assertIn('pageSize', pagination)
        self.assertIn('totalItems', pagination)
        self.assertIn('totalPages', pagination)

    def test_default_page_size_is_ten(self):
        response = self.client.get(LIST_URL)
        body = response.json()
        self.assertEqual(len(body['data']), 10)
        self.assertEqual(body['pagination']['pageSize'], 10)

    def test_total_items_counts_only_active_visible_hackathons(self):
        response = self.client.get(LIST_URL)
        body = response.json()
        self.assertEqual(body['pagination']['totalItems'], 12)

    def test_total_pages_calculation(self):
        response = self.client.get(LIST_URL)
        body = response.json()
        self.assertEqual(body['pagination']['totalPages'], 2)

    def test_default_is_page_one(self):
        response = self.client.get(LIST_URL)
        self.assertEqual(response.json()['pagination']['page'], 1)

    # --- Custom page / pageSize ---

    def test_custom_page_size(self):
        response = self.client.get(LIST_URL, {'page': 1, 'pageSize': 5})
        body = response.json()
        self.assertEqual(len(body['data']), 5)
        self.assertEqual(body['pagination']['pageSize'], 5)
        self.assertEqual(body['pagination']['totalPages'], 3)

    def test_page_two_returns_remaining_items(self):
        response = self.client.get(LIST_URL, {'page': 2, 'pageSize': 10})
        body = response.json()
        self.assertEqual(len(body['data']), 2)
        self.assertEqual(body['pagination']['page'], 2)

    def test_page_two_items_differ_from_page_one(self):
        page1 = self.client.get(LIST_URL, {'page': 1, 'pageSize': 10}).json()['data']
        page2 = self.client.get(LIST_URL, {'page': 2, 'pageSize': 10}).json()['data']
        ids_page1 = {h['id'] for h in page1}
        ids_page2 = {h['id'] for h in page2}
        self.assertTrue(ids_page1.isdisjoint(ids_page2))

    def test_out_of_range_page_returns_empty_data(self):
        response = self.client.get(LIST_URL, {'page': 999})
        body = response.json()
        self.assertEqual(body['data'], [])
        self.assertEqual(body['pagination']['totalItems'], 12)

    # --- limit param ---

    def test_limit_returns_correct_count(self):
        response = self.client.get(LIST_URL, {'limit': 4})
        body = response.json()
        self.assertIn('data', body)
        self.assertEqual(len(body['data']), 4)

    def test_limit_response_has_no_pagination_block(self):
        response = self.client.get(LIST_URL, {'limit': 4})
        body = response.json()
        self.assertNotIn('pagination', body)
        self.assertEqual(body['limit'], 4)

    def test_limit_larger_than_total_returns_all_active(self):
        response = self.client.get(LIST_URL, {'limit': 100})
        body = response.json()
        self.assertEqual(len(body['data']), 12)

    def test_limit_of_one_returns_single_item(self):
        response = self.client.get(LIST_URL, {'limit': 1})
        body = response.json()
        self.assertEqual(len(body['data']), 1)

    def test_invalid_string_limit_returns_400(self):
        response = self.client.get(LIST_URL, {'limit': 'abc'})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_negative_limit_returns_400(self):
        response = self.client.get(LIST_URL, {'limit': -1})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_zero_limit_returns_400(self):
        response = self.client.get(LIST_URL, {'limit': 0})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    # --- Filtering ---

    def test_ended_hackathons_excluded(self):
        response = self.client.get(LIST_URL, {'limit': 100})
        titles = [h['title'] for h in response.json()['data']]
        self.assertNotIn('Ended Hackathon', titles)

    def test_private_hackathons_excluded(self):
        response = self.client.get(LIST_URL, {'limit': 100})
        titles = [h['title'] for h in response.json()['data']]
        self.assertNotIn('Private Hackathon', titles)

    # --- Ordering ---

    def test_results_ordered_newest_first(self):
        response = self.client.get(LIST_URL, {'limit': 100})
        items = response.json()['data']
        for i in range(len(items) - 1):
            self.assertGreaterEqual(items[i]['created_at'], items[i + 1]['created_at'])

    def test_limit_returns_most_recent_items(self):
        # The 12th hackathon created is the most recent; limit=1 should return it
        all_response = self.client.get(LIST_URL, {'limit': 100})
        all_items = all_response.json()['data']
        most_recent_id = all_items[0]['id']

        limit_response = self.client.get(LIST_URL, {'limit': 1})
        self.assertEqual(limit_response.json()['data'][0]['id'], most_recent_id)

    # --- Auth ---

    def test_list_is_accessible_without_authentication(self):
        self.client.logout()
        response = self.client.get(LIST_URL)
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class HackathonRetrieveByNameTests(APITestCase):

    def setUp(self):
        cache.clear()
        self.organizer = make_user(1)
        self.org = make_org(self.organizer)
        self.hackathon = make_hackathon(self.org, title='Global Hackathon')

    def test_retrieve_by_slugified_name_returns_full_details(self):
        response = self.client.get(LIST_URL, {'hackathon_name': 'global_hackathon'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        body = response.json()
        self.assertEqual(body['hackathon']['title'], 'Global Hackathon')
        self.assertIn('teams', body)
        self.assertIn('individual_participants', body)
        self.assertIn('submissions', body)
        self.assertIn('projects', body)

    def test_retrieve_by_title_returns_full_details(self):
        response = self.client.get(LIST_URL, {'hackathon_name': 'Global Hackathon'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()['hackathon']['id'], self.hackathon.id)

    def test_missing_hackathon_name_returns_400(self):
        response = self.client.get(LIST_URL, {'hackathon_name': ''})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_unknown_hackathon_name_returns_404(self):
        response = self.client.get(LIST_URL, {'hackathon_name': 'nonexistent_hackathon'})
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_retrieve_by_name_is_accessible_without_authentication(self):
        self.client.logout()
        response = self.client.get(LIST_URL, {'hackathon_name': 'global_hackathon'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)


CREATE_URL = '/api/v1/hackathon/create/'


class HackathonCreateTests(APITestCase):

    def setUp(self):
        cache.clear()
        self.organizer = make_user(50)
        self.organizer.is_organizer = True
        self.organizer.save()
        self.org = make_org(self.organizer)
        self.client.force_authenticate(self.organizer)

    def valid_payload(self, **overrides):
        start = date.today() + timedelta(days=1)
        end = start + timedelta(days=5)
        payload = {
            'organization_id': self.org.id,
            'title': 'My Hackathon',
            'description': '<p>Build things</p>',
            'venue': 'Virtual',
            'visibility': True,
            'start_date': start.isoformat(),
            'end_date': end.isoformat(),
            'submission_deadline': f'{end.isoformat()}T23:59:59',
            'min_team_size': 1,
            'max_team_size': 5,
        }
        payload.update(overrides)
        return payload

    def test_create_without_banner_succeeds(self):
        res = self.client.post(CREATE_URL, self.valid_payload(), format='json')
        self.assertEqual(res.status_code, status.HTTP_201_CREATED, res.data)
        self.assertTrue(Hackathon.objects.filter(title='My Hackathon').exists())

    def test_null_banner_is_accepted(self):
        res = self.client.post(CREATE_URL, self.valid_payload(banner_image_file=None), format='json')
        self.assertEqual(res.status_code, status.HTTP_201_CREATED, res.data)

    def test_skills_are_saved(self):
        from accounts.models import Skill
        s1 = Skill.objects.create(name='Solidity')
        s2 = Skill.objects.create(name='React')
        res = self.client.post(CREATE_URL, self.valid_payload(skills=[s1.id, s2.id]), format='json')
        self.assertEqual(res.status_code, status.HTTP_201_CREATED, res.data)
        hackathon = Hackathon.objects.get(title='My Hackathon')
        self.assertEqual(set(hackathon.skills.values_list('id', flat=True)), {s1.id, s2.id})

    def test_missing_fields_return_all_field_errors_with_friendly_messages(self):
        res = self.client.post(CREATE_URL, {'organization_id': self.org.id}, format='json')
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        errors = res.data['errors']
        for field in ('title', 'description', 'venue', 'start_date', 'end_date', 'submission_deadline'):
            self.assertIn(field, errors)
        self.assertEqual(errors['venue'], ['Venue / location is required.'])
        self.assertIn('message', res.data)

    def test_cross_field_errors_are_keyed_by_field(self):
        start = date.today() + timedelta(days=5)
        payload = self.valid_payload(
            start_date=start.isoformat(),
            end_date=(start - timedelta(days=1)).isoformat(),
            min_team_size=6,
            max_team_size=2,
        )
        res = self.client.post(CREATE_URL, payload, format='json')
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('end_date', res.data['errors'])
        self.assertIn('max_team_size', res.data['errors'])

    def test_deadline_after_end_date_rejected(self):
        payload = self.valid_payload()
        end = date.fromisoformat(payload['end_date'])
        payload['submission_deadline'] = f'{(end + timedelta(days=1)).isoformat()}T23:59:59'
        res = self.client.post(CREATE_URL, payload, format='json')
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('submission_deadline', res.data['errors'])

    def test_unknown_organization_is_reported_on_organization_id(self):
        res = self.client.post(CREATE_URL, self.valid_payload(organization_id=99999), format='json')
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('organization_id', res.data['errors'])
