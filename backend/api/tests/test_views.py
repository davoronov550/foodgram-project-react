"""Интеграционные тесты вьюсетов и эндпоинтов приложения api."""
import base64
import shutil
import tempfile

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from recipes.models import (
    FavoriteRecipe,
    Ingredient,
    Recipe,
    RecipeIngredient,
    RecipeShoppingList,
    Tag,
)
from users.models import Follow

User = get_user_model()

TEMP_MEDIA_ROOT = tempfile.mkdtemp()

SMALL_GIF = (
    b'\x47\x49\x46\x38\x39\x61\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00'
    b'\xff\xff\xff\x21\xf9\x04\x00\x00\x00\x00\x00\x2c\x00\x00\x00\x00'
    b'\x01\x00\x01\x00\x00\x02\x02\x4c\x01\x00\x3b'
)


def base64_image():
    """base64-строка картинки для Base64ImageField."""
    encoded = base64.b64encode(SMALL_GIF).decode()
    return f'data:image/gif;base64,{encoded}'


def image_file(name='test.gif'):
    return SimpleUploadedFile(name, SMALL_GIF, content_type='image/gif')


def create_user(suffix='1', password='Pass!2345'):
    return User.objects.create_user(
        username=f'user{suffix}',
        email=f'user{suffix}@example.com',
        password=password,
        first_name='Имя',
        last_name='Фамилия',
    )


def create_recipe(author, name='Рецепт', cooking_time=30):
    return Recipe.objects.create(
        author=author,
        name=name,
        image=image_file(f'{name}.gif'),
        text='Описание',
        cooking_time=cooking_time,
    )


def tearDownModule():
    shutil.rmtree(TEMP_MEDIA_ROOT, ignore_errors=True)


class UserEndpointsTest(APITestCase):
    """Djoser + CustomUserViewSet: регистрация, токены, me, список/деталь."""

    @classmethod
    def setUpTestData(cls):
        cls.user = create_user('1')
        cls.other = create_user('2')

    def _register_payload(self, **overrides):
        data = {
            'email': 'newcomer@example.com',
            'username': 'newcomer',
            'first_name': 'Имя',
            'last_name': 'Фамилия',
            'password': 'Tasty!Meal7',
        }
        data.update(overrides)
        return data

    def test_registration_creates_user(self):
        response = self.client.post(
            '/api/users/', self._register_payload(), format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(
            set(response.data.keys()),
            {'email', 'id', 'username', 'first_name', 'last_name'})
        self.assertNotIn('password', response.data)
        self.assertTrue(
            User.objects.filter(email='newcomer@example.com').exists())

    def test_registration_password_not_returned(self):
        response = self.client.post(
            '/api/users/', self._register_payload(), format='json')
        self.assertNotIn('password', response.data)

    def test_token_login_returns_auth_token(self):
        response = self.client.post(
            '/api/auth/token/login/',
            {'email': 'user1@example.com', 'password': 'Pass!2345'},
            format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('auth_token', response.data)
        self.assertTrue(
            Token.objects.filter(key=response.data['auth_token']).exists())

    def test_token_logout_revokes_token(self):
        token = Token.objects.create(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')
        response = self.client.post('/api/auth/token/logout/')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Token.objects.filter(user=self.user).exists())

    def test_me_requires_authentication(self):
        response = self.client.get('/api/users/me/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_me_returns_current_user(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get('/api/users/me/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['email'], self.user.email)
        self.assertIn('is_subscribed', response.data)

    def test_user_list_available_to_anonymous(self):
        response = self.client.get('/api/users/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)

    def test_user_detail_available(self):
        response = self.client.get(f'/api/users/{self.user.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], self.user.id)


class SetPasswordTest(APITestCase):
    """C6: смена пароля с проверкой current_password."""

    def setUp(self):
        self.user = create_user('1')
        self.client.force_authenticate(user=self.user)

    def test_success_with_correct_current_password(self):
        response = self.client.post(
            '/api/users/set_password/',
            {'current_password': 'Pass!2345', 'new_password': 'New!Pass99'},
            format='json')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('New!Pass99'))

    def test_wrong_current_password_rejected(self):
        response = self.client.post(
            '/api/users/set_password/',
            {'current_password': 'WRONG', 'new_password': 'New!Pass99'},
            format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('current_password', response.data)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('Pass!2345'))

    def test_empty_current_password_rejected(self):
        response = self.client.post(
            '/api/users/set_password/',
            {'current_password': '', 'new_password': 'New!Pass99'},
            format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_missing_new_password_rejected(self):
        response = self.client.post(
            '/api/users/set_password/',
            {'current_password': 'Pass!2345'},
            format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)

    def test_requires_authentication(self):
        self.client.force_authenticate(user=None)
        response = self.client.post(
            '/api/users/set_password/',
            {'current_password': 'Pass!2345', 'new_password': 'New!Pass99'},
            format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class SubscribeTest(APITestCase):
    """subscribe/unsubscribe: успех, повтор, на себя, отсутствие."""

    @classmethod
    def setUpTestData(cls):
        cls.user = create_user('1')
        cls.author = create_user('2')

    def setUp(self):
        self.client.force_authenticate(user=self.user)

    def test_subscribe_success(self):
        response = self.client.post(
            f'/api/users/{self.author.id}/subscribe/')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(
            Follow.objects.filter(
                user=self.user, author=self.author).exists())
        self.assertTrue(response.data['is_subscribed'])
        self.assertIn('recipes', response.data)
        self.assertIn('recipes_count', response.data)

    def test_subscribe_duplicate_rejected(self):
        Follow.objects.create(user=self.user, author=self.author)
        response = self.client.post(
            f'/api/users/{self.author.id}/subscribe/')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)

    def test_subscribe_to_self_rejected(self):
        response = self.client.post(
            f'/api/users/{self.user.id}/subscribe/')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(
            Follow.objects.filter(
                user=self.user, author=self.user).exists())

    def test_subscribe_to_missing_user_404(self):
        response = self.client.post('/api/users/9999/subscribe/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_unsubscribe_success(self):
        Follow.objects.create(user=self.user, author=self.author)
        response = self.client.delete(
            f'/api/users/{self.author.id}/subscribe/')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(
            Follow.objects.filter(
                user=self.user, author=self.author).exists())

    def test_unsubscribe_when_not_subscribed_rejected(self):
        response = self.client.delete(
            f'/api/users/{self.author.id}/subscribe/')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)

    def test_subscribe_requires_authentication(self):
        self.client.force_authenticate(user=None)
        response = self.client.post(
            f'/api/users/{self.author.id}/subscribe/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


@override_settings(MEDIA_ROOT=TEMP_MEDIA_ROOT)
class SubscriptionsListTest(APITestCase):
    """subscriptions: пагинация и recipes_limit."""

    @classmethod
    def setUpTestData(cls):
        cls.user = create_user('1')
        cls.author = create_user('2')
        Follow.objects.create(user=cls.user, author=cls.author)
        for i in range(3):
            create_recipe(cls.author, name=f'Рецепт {i}')

    def setUp(self):
        self.client.force_authenticate(user=self.user)

    def test_paginated_response(self):
        response = self.client.get('/api/users/subscriptions/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            set(response.data.keys()),
            {'count', 'next', 'previous', 'results'})
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['id'], self.author.id)

    def test_recipes_count_full(self):
        response = self.client.get('/api/users/subscriptions/')
        author_data = response.data['results'][0]
        self.assertEqual(author_data['recipes_count'], 3)
        self.assertEqual(len(author_data['recipes']), 3)

    def test_recipes_limit_applied(self):
        response = self.client.get(
            '/api/users/subscriptions/?recipes_limit=2')
        author_data = response.data['results'][0]
        self.assertEqual(len(author_data['recipes']), 2)
        self.assertEqual(author_data['recipes_count'], 3)

    def test_requires_authentication(self):
        self.client.force_authenticate(user=None)
        response = self.client.get('/api/users/subscriptions/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


@override_settings(MEDIA_ROOT=TEMP_MEDIA_ROOT)
class RecipeReadTest(APITestCase):
    """RecipeViewSet: list/retrieve доступны анониму."""

    @classmethod
    def setUpTestData(cls):
        cls.author = create_user('1')
        cls.recipe = create_recipe(cls.author)

    def test_list_available_to_anonymous(self):
        response = self.client.get('/api/recipes/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            set(response.data.keys()),
            {'count', 'next', 'previous', 'results'})

    def test_retrieve_available_to_anonymous(self):
        response = self.client.get(f'/api/recipes/{self.recipe.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], self.recipe.id)
        self.assertIn('is_favorited', response.data)
        self.assertEqual(response.data['author']['id'], self.author.id)

    def test_anonymous_filter_by_is_favorited_does_not_crash(self):
        """Аноним с ?is_favorited=1 получает 200, а не 500."""
        response = self.client.get('/api/recipes/?is_favorited=1')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['results'], [])

    def test_anonymous_filter_by_shopping_cart_does_not_crash(self):
        """Аноним с ?is_in_shopping_cart=1 получает 200, а не 500."""
        response = self.client.get('/api/recipes/?is_in_shopping_cart=1')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['results'], [])


@override_settings(MEDIA_ROOT=TEMP_MEDIA_ROOT)
class RecipeWriteTest(APITestCase):
    """RecipeViewSet: create/update/destroy и права автора (H6)."""

    @classmethod
    def setUpTestData(cls):
        cls.author = create_user('1')
        cls.other = create_user('2')
        cls.tag = Tag.objects.create(
            name='Обед', color='#0000AA', slug='lunch')
        cls.ingredient = Ingredient.objects.create(name='Рис', unit='г')

    def _payload(self, **overrides):
        data = {
            'name': 'Плов',
            'text': 'Описание',
            'cooking_time': 60,
            'image': base64_image(),
            'tags': [self.tag.id],
            'ingredients': [{'id': self.ingredient.id, 'amount': 100}],
        }
        data.update(overrides)
        return data

    def test_create_requires_authentication(self):
        response = self.client.post(
            '/api/recipes/', self._payload(), format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_create_by_authenticated_user(self):
        self.client.force_authenticate(user=self.author)
        response = self.client.post(
            '/api/recipes/', self._payload(), format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        recipe = Recipe.objects.get(name='Плов')
        self.assertEqual(recipe.author, self.author)
        self.assertEqual(recipe.recipeingredient_set.count(), 1)

    def test_update_by_author(self):
        recipe = create_recipe(self.author, name='Старое')
        self.client.force_authenticate(user=self.author)
        response = self.client.patch(
            f'/api/recipes/{recipe.id}/',
            self._payload(name='Новое'), format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        recipe.refresh_from_db()
        self.assertEqual(recipe.name, 'Новое')

    def test_update_by_other_user_forbidden(self):
        recipe = create_recipe(self.author, name='Старое')
        self.client.force_authenticate(user=self.other)
        response = self.client.patch(
            f'/api/recipes/{recipe.id}/',
            self._payload(name='Чужое'), format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        recipe.refresh_from_db()
        self.assertEqual(recipe.name, 'Старое')

    def test_update_by_anonymous_unauthorized(self):
        recipe = create_recipe(self.author, name='Старое')
        response = self.client.patch(
            f'/api/recipes/{recipe.id}/',
            self._payload(name='Чужое'), format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_destroy_by_author(self):
        recipe = create_recipe(self.author, name='Удаляемый')
        self.client.force_authenticate(user=self.author)
        response = self.client.delete(f'/api/recipes/{recipe.id}/')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Recipe.objects.filter(id=recipe.id).exists())

    def test_destroy_by_other_user_forbidden(self):
        recipe = create_recipe(self.author, name='Удаляемый')
        self.client.force_authenticate(user=self.other)
        response = self.client.delete(f'/api/recipes/{recipe.id}/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(Recipe.objects.filter(id=recipe.id).exists())

    def test_destroy_by_anonymous_unauthorized(self):
        recipe = create_recipe(self.author, name='Удаляемый')
        response = self.client.delete(f'/api/recipes/{recipe.id}/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


@override_settings(MEDIA_ROOT=TEMP_MEDIA_ROOT)
class FavoriteAndShoppingCartTest(APITestCase):
    """favorite/shopping_cart: добавление, повтор (400), DELETE (C5)."""

    @classmethod
    def setUpTestData(cls):
        cls.user = create_user('1')
        cls.author = create_user('2')
        cls.recipe = create_recipe(cls.author)

    def setUp(self):
        self.client.force_authenticate(user=self.user)

    def test_favorite_add(self):
        response = self.client.post(
            f'/api/recipes/{self.recipe.id}/favorite/')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(
            FavoriteRecipe.objects.filter(
                user=self.user, recipe=self.recipe).exists())

    def test_favorite_duplicate_rejected(self):
        FavoriteRecipe.objects.create(user=self.user, recipe=self.recipe)
        response = self.client.post(
            f'/api/recipes/{self.recipe.id}/favorite/')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_favorite_delete_success(self):
        FavoriteRecipe.objects.create(user=self.user, recipe=self.recipe)
        response = self.client.delete(
            f'/api/recipes/{self.recipe.id}/favorite/')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(
            FavoriteRecipe.objects.filter(
                user=self.user, recipe=self.recipe).exists())

    def test_favorite_delete_missing_returns_400_dict(self):
        response = self.client.delete(
            f'/api/recipes/{self.recipe.id}/favorite/')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIsInstance(response.data, dict)
        self.assertIn('error', response.data)

    def test_shopping_cart_add(self):
        response = self.client.post(
            f'/api/recipes/{self.recipe.id}/shopping_cart/')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(
            RecipeShoppingList.objects.filter(
                user=self.user, recipe=self.recipe).exists())

    def test_shopping_cart_duplicate_rejected(self):
        RecipeShoppingList.objects.create(user=self.user, recipe=self.recipe)
        response = self.client.post(
            f'/api/recipes/{self.recipe.id}/shopping_cart/')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_shopping_cart_delete_missing_returns_400_dict(self):
        response = self.client.delete(
            f'/api/recipes/{self.recipe.id}/shopping_cart/')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIsInstance(response.data, dict)
        self.assertIn('error', response.data)

    def test_favorite_requires_authentication(self):
        self.client.force_authenticate(user=None)
        response = self.client.post(
            f'/api/recipes/{self.recipe.id}/favorite/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


@override_settings(MEDIA_ROOT=TEMP_MEDIA_ROOT)
class DownloadShoppingCartTest(APITestCase):
    """download_shopping_cart: C4 (auth), агрегация, имя файла (H10)."""

    @classmethod
    def setUpTestData(cls):
        cls.user = create_user('1')
        cls.rice = Ingredient.objects.create(name='Рис', unit='г')
        cls.salt = Ingredient.objects.create(name='Соль', unit='г')
        cls.recipe1 = create_recipe(cls.user, name='Плов')
        cls.recipe2 = create_recipe(cls.user, name='Каша')
        RecipeIngredient.objects.create(
            recipe=cls.recipe1, ingredient=cls.rice, amount=100)
        RecipeIngredient.objects.create(
            recipe=cls.recipe1, ingredient=cls.salt, amount=5)
        RecipeIngredient.objects.create(
            recipe=cls.recipe2, ingredient=cls.rice, amount=50)
        RecipeShoppingList.objects.create(user=cls.user, recipe=cls.recipe1)
        RecipeShoppingList.objects.create(user=cls.user, recipe=cls.recipe2)

    def test_requires_authentication(self):
        response = self.client.get('/api/recipes/download_shopping_cart/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_content_type_and_filename(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get('/api/recipes/download_shopping_cart/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response['Content-Type'], 'text/plain')
        disposition = response['Content-Disposition']
        self.assertIn('shopping_list.txt', disposition)
        self.assertNotIn('.txt.txt', disposition)

    def test_aggregates_duplicate_ingredients(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get('/api/recipes/download_shopping_cart/')
        content = response.content.decode()
        # Рис суммируется из двух рецептов: 100 + 50 = 150
        self.assertIn('Рис', content)
        self.assertIn('150', content)
        self.assertIn('Соль', content)


class TagViewSetTest(APITestCase):
    """TagViewSet: list/retrieve без пагинации."""

    @classmethod
    def setUpTestData(cls):
        cls.tag = Tag.objects.create(
            name='Завтрак', color='#AA0000', slug='breakfast')

    def test_list_is_not_paginated(self):
        response = self.client.get('/api/tags/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(response.data, list)
        self.assertEqual(response.data[0]['slug'], 'breakfast')

    def test_retrieve(self):
        response = self.client.get(f'/api/tags/{self.tag.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['slug'], 'breakfast')


class IngredientViewSetTest(APITestCase):
    """IngredientViewSet: list/retrieve, без пагинации, поиск по ?name=."""

    @classmethod
    def setUpTestData(cls):
        cls.rice = Ingredient.objects.create(name='Рис', unit='г')
        cls.salt = Ingredient.objects.create(name='Соль', unit='г')
        cls.sugar = Ingredient.objects.create(name='Сахар', unit='г')

    def test_list_is_not_paginated(self):
        response = self.client.get('/api/ingredients/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(response.data, list)
        self.assertEqual(len(response.data), 3)

    def test_retrieve(self):
        response = self.client.get(f'/api/ingredients/{self.rice.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['name'], 'Рис')
        self.assertEqual(response.data['measurement_unit'], 'г')

    def test_search_by_name(self):
        response = self.client.get('/api/ingredients/?name=Са')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        names = {item['name'] for item in response.data}
        self.assertEqual(names, {'Сахар'})

    def test_search_no_match(self):
        response = self.client.get('/api/ingredients/?name=Перец')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, [])
