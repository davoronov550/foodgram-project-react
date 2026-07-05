"""Верификация Google ID-token (GIS) и связывание с аккаунтом Foodgram."""
import logging

from django.conf import settings
from django.db import transaction
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token
from rest_framework import serializers

from users.models import GoogleAccount, User

logger = logging.getLogger(__name__)

MAX_USERNAME_LENGTH = 150
USERNAME_EXTRA_CHARS = '.@+-_'


class GoogleAuthError(serializers.ValidationError):
    """Ошибка аутентификации через Google (транслируется DRF в HTTP 400)."""


def verify_google_token(credential):
    """
    Проверяет подпись, aud (наш client_id), iss и срок действия ID-token
    и возвращает его расшифрованный payload. Публичные ключи Google
    кэшируются библиотекой — сетевой запрос не выполняется на каждый вызов.
    """
    try:
        payload = id_token.verify_oauth2_token(
            credential,
            google_requests.Request(),
            settings.GOOGLE_OAUTH_CLIENT_ID,
        )
    except ValueError as error:
        logger.warning('Отклонён Google ID-token: %s', error)
        raise GoogleAuthError('Недействительный токен Google.')
    return payload


def _sanitize_username(value):
    """Оставляет только допустимые для username символы."""
    allowed = ''.join(
        char for char in value
        if char.isalnum() or char in USERNAME_EXTRA_CHARS
    )
    return allowed[:MAX_USERNAME_LENGTH] or 'user'


def _unique_username(base):
    """Уникальный username: добавляет числовой суффикс при коллизии."""
    candidate = _sanitize_username(base)
    if not User.objects.filter(username=candidate).exists():
        return candidate
    counter = 1
    while True:
        suffix = str(counter)
        trimmed = candidate[:MAX_USERNAME_LENGTH - len(suffix)]
        numbered = f'{trimmed}{suffix}'
        if not User.objects.filter(username=numbered).exists():
            return numbered
        counter += 1


@transaction.atomic
def get_or_create_user_from_google(payload):
    """
    По payload от Google возвращает пользователя Foodgram:
    - повторный вход (по стабильному sub) → существующий пользователь;
    - совпадение подтверждённого email → привязка к существующему аккаунту;
    - иначе → создание нового пользователя без пароля.
    """
    google_sub = payload['sub']
    email = payload.get('email', '')
    if not payload.get('email_verified'):
        raise GoogleAuthError('Google не подтвердил адрес электронной почты.')

    account = GoogleAccount.objects.filter(google_sub=google_sub).first()
    if account is not None:
        return account.user

    user = User.objects.filter(email__iexact=email).first()
    if user is None:
        user = User.objects.create(
            username=_unique_username(email.split('@')[0]),
            email=email,
            first_name=payload.get('given_name', ''),
            last_name=payload.get('family_name', ''),
        )
        user.set_unusable_password()
        user.save(update_fields=['password'])

    GoogleAccount.objects.create(
        user=user, google_sub=google_sub, email=email
    )
    return user
