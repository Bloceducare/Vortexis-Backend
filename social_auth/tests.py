from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from social_auth.utils import Github

GITHUB_URL = '/api/v1/auth/github'


class GithubGetPrimaryEmailTests(SimpleTestCase):
    """Unit tests for the /user/emails parsing itself (no DB, no HTTP)."""

    def _mock_get(self, payload):
        resp = MagicMock()
        resp.json.return_value = payload
        return resp

    @patch('social_auth.utils.requests.get')
    def test_picks_primary_verified(self, mock_get):
        mock_get.return_value = self._mock_get([
            {'email': 'secondary@x.com', 'primary': False, 'verified': True},
            {'email': 'primary@x.com', 'primary': True, 'verified': True},
        ])
        self.assertEqual(Github.get_primary_email('tok'), 'primary@x.com')

    @patch('social_auth.utils.requests.get')
    def test_skips_unverified_primary_uses_verified(self, mock_get):
        mock_get.return_value = self._mock_get([
            {'email': 'primary@x.com', 'primary': True, 'verified': False},
            {'email': 'verified@x.com', 'primary': False, 'verified': True},
        ])
        self.assertEqual(Github.get_primary_email('tok'), 'verified@x.com')

    @patch('social_auth.utils.requests.get')
    def test_none_when_nothing_verified(self, mock_get):
        mock_get.return_value = self._mock_get([
            {'email': 'a@x.com', 'primary': True, 'verified': False},
        ])
        self.assertIsNone(Github.get_primary_email('tok'))

    @patch('social_auth.utils.requests.get')
    def test_none_on_error_payload(self, mock_get):
        # GitHub returns a dict (not a list) on auth failure
        mock_get.return_value = self._mock_get({'message': 'Bad credentials'})
        self.assertIsNone(Github.get_primary_email('tok'))

    @patch('social_auth.utils.requests.get', side_effect=Exception('network down'))
    def test_none_on_request_exception(self, mock_get):
        self.assertIsNone(Github.get_primary_email('tok'))


class GithubSocialAuthTests(APITestCase):
    """GitHub OAuth registration/login flow.

    The GitHub HTTP calls are mocked so these run without network access. We
    patch the three points of contact with GitHub:
      - Github.get_token        -> exchanges the code for an access token
      - Github.get_user_details -> GET /user
      - Github.get_primary_email-> GET /user/emails (private-email fallback)
    """

    def _post(self, code='valid-code'):
        return self.client.post(GITHUB_URL, {'code': code})

    # --- Bug 1: private emails fall back to /user/emails -----------------

    @patch('social_auth.serializer.Github.get_primary_email')
    @patch('social_auth.serializer.Github.get_user_details')
    @patch('social_auth.serializer.Github.get_token')
    def test_private_email_falls_back_to_user_emails(self, mock_token, mock_user, mock_email):
        mock_token.return_value = 'gho_token'
        # GitHub returns email: null for a private email
        mock_user.return_value = {'login': 'octocat', 'name': 'Mona Cat', 'email': None}
        mock_email.return_value = 'mona@private.example.com'

        response = self._post()

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        mock_email.assert_called_once()
        user = User.objects.get(email='mona@private.example.com')
        self.assertEqual(user.username, 'octocat')
        self.assertEqual(user.first_name, 'Mona')
        self.assertEqual(user.last_name, 'Cat')

    @patch('social_auth.serializer.Github.get_primary_email')
    @patch('social_auth.serializer.Github.get_user_details')
    @patch('social_auth.serializer.Github.get_token')
    def test_public_email_does_not_need_fallback(self, mock_token, mock_user, mock_email):
        mock_token.return_value = 'gho_token'
        mock_user.return_value = {'login': 'octocat', 'name': 'Mona Cat', 'email': 'mona@public.example.com'}

        response = self._post()

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        mock_email.assert_not_called()
        self.assertTrue(User.objects.filter(email='mona@public.example.com').exists())

    @patch('social_auth.serializer.Github.get_primary_email')
    @patch('social_auth.serializer.Github.get_user_details')
    @patch('social_auth.serializer.Github.get_token')
    def test_no_email_anywhere_returns_400(self, mock_token, mock_user, mock_email):
        mock_token.return_value = 'gho_token'
        mock_user.return_value = {'login': 'octocat', 'name': 'Mona Cat', 'email': None}
        mock_email.return_value = None

        response = self._post()

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('email', response.json())

    # --- Bug 2: missing/partial names must not 500 -----------------------

    @patch('social_auth.serializer.Github.get_user_details')
    @patch('social_auth.serializer.Github.get_token')
    def test_no_name_falls_back_to_login(self, mock_token, mock_user):
        mock_token.return_value = 'gho_token'
        mock_user.return_value = {'login': 'octocat', 'name': None, 'email': 'a@example.com'}

        response = self._post()

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        user = User.objects.get(email='a@example.com')
        self.assertEqual(user.first_name, 'octocat')
        self.assertEqual(user.last_name, '')

    @patch('social_auth.serializer.Github.get_user_details')
    @patch('social_auth.serializer.Github.get_token')
    def test_single_name_leaves_last_name_empty(self, mock_token, mock_user):
        mock_token.return_value = 'gho_token'
        mock_user.return_value = {'login': 'octocat', 'name': 'Mona', 'email': 'b@example.com'}

        response = self._post()

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        user = User.objects.get(email='b@example.com')
        self.assertEqual(user.first_name, 'Mona')
        self.assertEqual(user.last_name, '')

    @patch('social_auth.serializer.Github.get_user_details')
    @patch('social_auth.serializer.Github.get_token')
    def test_multipart_last_name_is_preserved(self, mock_token, mock_user):
        mock_token.return_value = 'gho_token'
        mock_user.return_value = {'login': 'octocat', 'name': 'Mona Lisa Cat', 'email': 'c@example.com'}

        response = self._post()

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        user = User.objects.get(email='c@example.com')
        self.assertEqual(user.first_name, 'Mona')
        self.assertEqual(user.last_name, 'Lisa Cat')

    @patch('social_auth.serializer.Github.get_user_details')
    @patch('social_auth.serializer.Github.get_token')
    def test_whitespace_only_name_falls_back_to_login(self, mock_token, mock_user):
        mock_token.return_value = 'gho_token'
        mock_user.return_value = {'login': 'octocat', 'name': '   ', 'email': 'd@example.com'}

        response = self._post()

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        user = User.objects.get(email='d@example.com')
        self.assertEqual(user.first_name, 'octocat')
        self.assertEqual(user.last_name, '')

    # --- Bug 3: invalid code is an auth failure (not a 500) --------------

    @patch('social_auth.serializer.Github.get_token')
    def test_invalid_code_returns_401(self, mock_token):
        mock_token.return_value = None

        response = self._post(code='bad-code')

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_missing_code_returns_400(self):
        response = self.client.post(GITHUB_URL, {})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    # --- Existing-user linking ------------------------------------------

    @patch('social_auth.serializer.Github.get_user_details')
    @patch('social_auth.serializer.Github.get_token')
    def test_existing_email_logs_in_without_duplicate(self, mock_token, mock_user):
        existing = User.objects.create_user(
            email='dupe@example.com', username='existing',
            first_name='Old', last_name='Name', password='pw12345',
        )
        mock_token.return_value = 'gho_token'
        mock_user.return_value = {'login': 'existing', 'name': 'Mona Cat', 'email': 'dupe@example.com'}

        response = self._post()

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(User.objects.filter(email='dupe@example.com').count(), 1)
        self.assertEqual(response.json()['id'], existing.id)
