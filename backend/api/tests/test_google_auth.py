"""Тесты входа/регистрации через Google (эндпоинт /api/auth/google/)."""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from api.google_auth import (
    GoogleAuthError,
    _unique_username,
    get_or_create_user_from_google,
    verify_google_token,
)
from users.models import GoogleAccount

User = get_user_model()

GOOGLE_URL = '/api/auth/google/'
CLIENT_ID = 'test-client-id.apps.googleusercontent.com'

VERIFY_TARGET = 'api.google_auth.id_token.verify_oauth2_token'


def google_payload(**overrides):
    """Собирает payload, аналогичный расшифрованному Google ID-token."""
    payload = {
        'sub': '1234567890',
        'email': 'newuser@example.com',
        'email_verified': True,
        'given_name': 'Иван',
        'family_name': 'Петров',
    }
    payload.update(overrides)
    return payload


def make_user(username='existing', email='existing@example.com'):
    return User.objects.create_user(
        username=username,
        email=email,
        password='Pass!2345',
        first_name='Имя',
        last_name='Фамилия',
    )


class UniqueUsernameTests(TestCase):
    """Юнит-тесты генерации уникального username."""

    def test_returns_base_when_free(self):
        self.assertEqual(_unique_username('ivan'), 'ivan')

    def test_sanitizes_disallowed_chars(self):
        # Пробелы и пунктуация удаляются; буквы (в т.ч. Unicode,
        # разрешённые Django по умолчанию) сохраняются.
        self.assertEqual(_unique_username('иван ivan!#'), 'иванivan')

    def test_appends_suffix_on_collision(self):
        make_user(username='ivan', email='ivan@example.com')
        self.assertEqual(_unique_username('ivan'), 'ivan1')

    def test_empty_base_falls_back_to_user(self):
        self.assertEqual(_unique_username('####'), 'user')


class GetOrCreateUserTests(TestCase):
    """Юнит-тесты сервиса связывания/создания пользователя."""

    def test_creates_new_user_without_password(self):
        user = get_or_create_user_from_google(google_payload())
        self.assertEqual(user.email, 'newuser@example.com')
        self.assertEqual(user.first_name, 'Иван')
        self.assertEqual(user.last_name, 'Петров')
        self.assertFalse(user.has_usable_password())
        self.assertTrue(
            GoogleAccount.objects.filter(user=user, google_sub='1234567890')
            .exists()
        )

    def test_links_existing_user_by_verified_email(self):
        existing = make_user(email='newuser@example.com', username='taken')
        user = get_or_create_user_from_google(google_payload())
        self.assertEqual(user.pk, existing.pk)
        self.assertTrue(existing.has_usable_password())
        self.assertTrue(hasattr(user, 'google_account'))

    def test_email_match_is_case_insensitive(self):
        existing = make_user(email='NewUser@Example.com', username='taken')
        user = get_or_create_user_from_google(google_payload())
        self.assertEqual(user.pk, existing.pk)

    def test_repeat_login_returns_same_user(self):
        first = get_or_create_user_from_google(google_payload())
        second = get_or_create_user_from_google(google_payload())
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(GoogleAccount.objects.count(), 1)

    def test_rejects_unverified_email(self):
        with self.assertRaises(GoogleAuthError):
            get_or_create_user_from_google(
                google_payload(email_verified=False)
            )
        self.assertEqual(User.objects.count(), 0)

    def test_missing_names_default_to_empty(self):
        payload = google_payload()
        del payload['given_name']
        del payload['family_name']
        user = get_or_create_user_from_google(payload)
        self.assertEqual(user.first_name, '')
        self.assertEqual(user.last_name, '')


@override_settings(GOOGLE_OAUTH_CLIENT_ID=CLIENT_ID)
class VerifyGoogleTokenTests(TestCase):
    """Юнит-тесты обёртки верификации токена."""

    def test_returns_payload_on_valid_token(self):
        with patch(VERIFY_TARGET, return_value=google_payload()) as mocked:
            payload = verify_google_token('valid-credential')
        mocked.assert_called_once()
        self.assertEqual(payload['sub'], '1234567890')

    def test_raises_google_auth_error_on_invalid_token(self):
        with patch(VERIFY_TARGET, side_effect=ValueError('bad token')):
            with self.assertRaises(GoogleAuthError):
                verify_google_token('broken-credential')


@override_settings(GOOGLE_OAUTH_CLIENT_ID=CLIENT_ID)
class GoogleAuthEndpointTests(APITestCase):
    """Интеграционные тесты эндпоинта /api/auth/google/."""

    def setUp(self):
        # Сбрасываем историю троттлинга между тестами, чтобы
        # ScopedRateThrottle не отдавал 429 из-за накопленных запросов.
        cache.clear()

    def test_new_user_gets_token_and_is_created(self):
        with patch(VERIFY_TARGET, return_value=google_payload()):
            response = self.client.post(
                GOOGLE_URL, {'credential': 'valid'}, format='json'
            )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('auth_token', response.data)
        user = User.objects.get(email='newuser@example.com')
        self.assertEqual(response.data['auth_token'],
                         Token.objects.get(user=user).key)

    def test_links_existing_account(self):
        existing = make_user(email='newuser@example.com', username='taken')
        with patch(VERIFY_TARGET, return_value=google_payload()):
            response = self.client.post(
                GOOGLE_URL, {'credential': 'valid'}, format='json'
            )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(User.objects.count(), 1)
        self.assertEqual(response.data['auth_token'],
                         Token.objects.get(user=existing).key)

    def test_idempotent_same_sub_returns_same_token(self):
        with patch(VERIFY_TARGET, return_value=google_payload()):
            first = self.client.post(
                GOOGLE_URL, {'credential': 'valid'}, format='json'
            )
            second = self.client.post(
                GOOGLE_URL, {'credential': 'valid'}, format='json'
            )
        self.assertEqual(first.data['auth_token'], second.data['auth_token'])
        self.assertEqual(User.objects.count(), 1)

    def test_unverified_email_returns_400(self):
        with patch(VERIFY_TARGET,
                   return_value=google_payload(email_verified=False)):
            response = self.client.post(
                GOOGLE_URL, {'credential': 'valid'}, format='json'
            )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(User.objects.count(), 0)

    def test_invalid_token_returns_400(self):
        with patch(VERIFY_TARGET, side_effect=ValueError('bad token')):
            response = self.client.post(
                GOOGLE_URL, {'credential': 'broken'}, format='json'
            )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_missing_credential_returns_400(self):
        response = self.client.post(GOOGLE_URL, {}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @override_settings(GOOGLE_OAUTH_CLIENT_ID=None)
    def test_returns_503_when_not_configured(self):
        response = self.client.post(
            GOOGLE_URL, {'credential': 'valid'}, format='json'
        )
        self.assertEqual(response.status_code,
                         status.HTTP_503_SERVICE_UNAVAILABLE)
