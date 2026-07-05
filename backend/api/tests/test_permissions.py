"""Тесты прав доступа приложения api (api/permissions.py)."""
import shutil
import tempfile

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory, TestCase, override_settings

from api.permissions import AuthorOnly
from recipes.models import Recipe

User = get_user_model()

TEMP_MEDIA_ROOT = tempfile.mkdtemp()

SMALL_GIF = (
    b'\x47\x49\x46\x38\x39\x61\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00'
    b'\xff\xff\xff\x21\xf9\x04\x00\x00\x00\x00\x00\x2c\x00\x00\x00\x00'
    b'\x01\x00\x01\x00\x00\x02\x02\x4c\x01\x00\x3b'
)


def create_user(suffix='1'):
    return User.objects.create_user(
        username=f'user{suffix}',
        email=f'user{suffix}@example.com',
        password='Pass!2345',
        first_name='Имя',
        last_name='Фамилия',
    )


def tearDownModule():
    shutil.rmtree(TEMP_MEDIA_ROOT, ignore_errors=True)


@override_settings(MEDIA_ROOT=TEMP_MEDIA_ROOT)
class AuthorOnlyTest(TestCase):
    """has_object_permission: SAFE-методы всем, запись только автору."""

    @classmethod
    def setUpTestData(cls):
        cls.author = create_user('1')
        cls.other = create_user('2')
        cls.recipe = Recipe.objects.create(
            author=cls.author,
            name='Рецепт',
            image=SimpleUploadedFile(
                'r.gif', SMALL_GIF, content_type='image/gif'),
            text='Описание',
            cooking_time=30,
        )

    def setUp(self):
        self.permission = AuthorOnly()
        self.factory = RequestFactory()

    def _request(self, method, user):
        request = getattr(self.factory, method)('/')
        request.user = user
        return request

    def test_safe_method_allowed_for_author(self):
        request = self._request('get', self.author)
        self.assertTrue(
            self.permission.has_object_permission(
                request, None, self.recipe))

    def test_safe_method_allowed_for_other_user(self):
        request = self._request('get', self.other)
        self.assertTrue(
            self.permission.has_object_permission(
                request, None, self.recipe))

    def test_safe_method_allowed_for_anonymous(self):
        request = self._request('get', AnonymousUser())
        self.assertTrue(
            self.permission.has_object_permission(
                request, None, self.recipe))

    def test_unsafe_method_allowed_for_author(self):
        for method in ('patch', 'put', 'delete'):
            with self.subTest(method=method):
                request = self._request(method, self.author)
                self.assertTrue(
                    self.permission.has_object_permission(
                        request, None, self.recipe))

    def test_unsafe_method_forbidden_for_other_user(self):
        for method in ('patch', 'put', 'delete'):
            with self.subTest(method=method):
                request = self._request(method, self.other)
                self.assertFalse(
                    self.permission.has_object_permission(
                        request, None, self.recipe))

    def test_unsafe_method_forbidden_for_anonymous(self):
        request = self._request('delete', AnonymousUser())
        self.assertFalse(
            self.permission.has_object_permission(
                request, None, self.recipe))
