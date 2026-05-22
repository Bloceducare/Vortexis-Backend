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
