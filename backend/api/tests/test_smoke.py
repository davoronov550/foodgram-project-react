from http import HTTPStatus

from django.test import Client, TestCase


class RecipeBookAPITestCase(TestCase):
    """Базовая проверка доступности сервиса."""

    def setUp(self):
        self.guest_client = Client()

    def test_list_exists(self):
        """Список рецептов доступен анонимному пользователю."""
        response = self.guest_client.get('/api/recipes/')
        self.assertEqual(response.status_code, HTTPStatus.OK)
