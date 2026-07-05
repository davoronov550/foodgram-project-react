"""Тесты сериализаторов приложения api."""
import base64
import shutil
import tempfile

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory

from api.serializers import (
    CustomUserCreateSerializer,
    CustomUserSerializer,
    FavoriteRecipeSerializer,
    IngredientSerializer,
    RecipeCreateUpdateSerializer,
    RecipeIngredientSerializer,
    RecipeSerializer,
    RecipeShoppingListSerializer,
    RecipeShortSerializer,
    SubscriptionsSerializer,
    TagSerializer,
)
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


def create_user(suffix='1'):
    return User.objects.create_user(
        username=f'user{suffix}',
        email=f'user{suffix}@example.com',
        password='Pass!2345',
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


def make_request(user=None, query=''):
    """DRF Request с заданным user и query-параметрами."""
    factory = APIRequestFactory()
    path = '/' + (f'?{query}' if query else '')
    request = Request(factory.get(path))
    request.user = user if user is not None else AnonymousUser()
    return request


def tearDownModule():
    shutil.rmtree(TEMP_MEDIA_ROOT, ignore_errors=True)


class CustomUserCreateSerializerTest(TestCase):
    """C7: запрет username=me и mass-assignment прав."""

    def _payload(self, **overrides):
        data = {
            'email': 'newcomer@example.com',
            'username': 'newcomer',
            'first_name': 'Имя',
            'last_name': 'Фамилия',
            'password': 'Tasty!Meal7',
        }
        data.update(overrides)
        return data

    def test_username_me_rejected(self):
        serializer = CustomUserCreateSerializer(
            data=self._payload(username='me'))
        self.assertFalse(serializer.is_valid())
        self.assertIn('username', serializer.errors)

    def test_valid_user_created(self):
        serializer = CustomUserCreateSerializer(data=self._payload())
        self.assertTrue(serializer.is_valid(), serializer.errors)
        user = serializer.save()
        self.assertTrue(user.check_password('Tasty!Meal7'))
        # пароль не возвращается в выводе
        self.assertNotIn('password', serializer.data)

    def test_mass_assignment_blocked(self):
        serializer = CustomUserCreateSerializer(
            data=self._payload(is_superuser=True, is_staff=True))
        self.assertTrue(serializer.is_valid(), serializer.errors)
        user = serializer.save()
        self.assertFalse(user.is_superuser)
        self.assertFalse(user.is_staff)


class CustomUserSerializerTest(TestCase):
    """get_is_subscribed: аноним / подписан / не подписан."""

    @classmethod
    def setUpTestData(cls):
        cls.author = create_user('1')
        cls.follower = create_user('2')
        cls.stranger = create_user('3')
        Follow.objects.create(user=cls.follower, author=cls.author)

    def test_anonymous_is_not_subscribed(self):
        data = CustomUserSerializer(
            self.author, context={'request': make_request()}).data
        self.assertFalse(data['is_subscribed'])

    def test_subscribed_true(self):
        data = CustomUserSerializer(
            self.author,
            context={'request': make_request(self.follower)}).data
        self.assertTrue(data['is_subscribed'])

    def test_not_subscribed_false(self):
        data = CustomUserSerializer(
            self.author,
            context={'request': make_request(self.stranger)}).data
        self.assertFalse(data['is_subscribed'])


class IngredientSerializerTest(TestCase):
    """C1: ингредиент отдаётся как measurement_unit."""

    @classmethod
    def setUpTestData(cls):
        cls.ingredient = Ingredient.objects.create(name='Соль', unit='г')

    def test_fields_and_measurement_unit(self):
        data = IngredientSerializer(self.ingredient).data
        self.assertEqual(
            set(data.keys()), {'id', 'name', 'measurement_unit'})
        self.assertEqual(data['measurement_unit'], 'г')
        self.assertNotIn('unit', data)


@override_settings(MEDIA_ROOT=TEMP_MEDIA_ROOT)
class RecipeIngredientSerializerTest(TestCase):
    """C1: связка рецепт-ингредиент отдаёт measurement_unit."""

    @classmethod
    def setUpTestData(cls):
        author = create_user('1')
        recipe = create_recipe(author)
        cls.ingredient = Ingredient.objects.create(name='Рис', unit='г')
        cls.link = RecipeIngredient.objects.create(
            recipe=recipe, ingredient=cls.ingredient, amount=150)

    def test_representation(self):
        data = RecipeIngredientSerializer(self.link).data
        self.assertEqual(
            set(data.keys()), {'id', 'name', 'measurement_unit', 'amount'})
        self.assertEqual(data['id'], self.ingredient.id)
        self.assertEqual(data['measurement_unit'], 'г')
        self.assertEqual(data['amount'], 150)


@override_settings(MEDIA_ROOT=TEMP_MEDIA_ROOT)
class RecipeShortSerializerTest(TestCase):
    """C2: краткий сериализатор содержит id и не содержит author."""

    @classmethod
    def setUpTestData(cls):
        cls.recipe = create_recipe(create_user('1'))

    def test_fields(self):
        data = RecipeShortSerializer(self.recipe).data
        self.assertEqual(
            set(data.keys()), {'id', 'name', 'image', 'cooking_time'})
        self.assertEqual(data['id'], self.recipe.id)
        self.assertNotIn('author', data)


@override_settings(MEDIA_ROOT=TEMP_MEDIA_ROOT)
class RecipeSerializerTest(TestCase):
    """C10: is_favorited/is_in_shopping_cart (аннотация + fallback)."""

    @classmethod
    def setUpTestData(cls):
        cls.author = create_user('1')
        cls.user = create_user('2')
        cls.tag = Tag.objects.create(
            name='Обед', color='#0000AA', slug='lunch')
        cls.ingredient = Ingredient.objects.create(name='Рис', unit='г')
        cls.recipe = create_recipe(cls.author)
        cls.recipe.tags.add(cls.tag)
        RecipeIngredient.objects.create(
            recipe=cls.recipe, ingredient=cls.ingredient, amount=100)

    def _recipe(self):
        """Свежий инстанс без аннотаций (для fallback-ветки)."""
        return Recipe.objects.get(pk=self.recipe.pk)

    def test_annotation_branch_used(self):
        recipe = self._recipe()
        recipe.is_favorited = True
        recipe.is_in_shopping_cart = True
        data = RecipeSerializer(
            recipe, context={'request': make_request(self.user)}).data
        self.assertTrue(data['is_favorited'])
        self.assertTrue(data['is_in_shopping_cart'])

    def test_fallback_true_when_in_lists(self):
        FavoriteRecipe.objects.create(user=self.user, recipe=self.recipe)
        RecipeShoppingList.objects.create(user=self.user, recipe=self.recipe)
        data = RecipeSerializer(
            self._recipe(),
            context={'request': make_request(self.user)}).data
        self.assertTrue(data['is_favorited'])
        self.assertTrue(data['is_in_shopping_cart'])

    def test_fallback_false_for_anonymous(self):
        data = RecipeSerializer(
            self._recipe(), context={'request': make_request()}).data
        self.assertFalse(data['is_favorited'])
        self.assertFalse(data['is_in_shopping_cart'])

    def test_composition(self):
        data = RecipeSerializer(
            self._recipe(),
            context={'request': make_request(self.user)}).data
        self.assertEqual(data['author']['id'], self.author.id)
        self.assertEqual(len(data['tags']), 1)
        self.assertEqual(data['tags'][0]['slug'], 'lunch')
        self.assertEqual(len(data['ingredients']), 1)
        self.assertEqual(
            data['ingredients'][0]['measurement_unit'], 'г')


@override_settings(MEDIA_ROOT=TEMP_MEDIA_ROOT)
class RecipeCreateUpdateSerializerTest(TestCase):
    """H7/H8/H9 + create/update/to_representation."""

    @classmethod
    def setUpTestData(cls):
        cls.author = create_user('1')
        cls.tag = Tag.objects.create(
            name='Обед', color='#0000AA', slug='lunch')
        cls.tag2 = Tag.objects.create(
            name='Ужин', color='#00AA00', slug='dinner')
        cls.ing1 = Ingredient.objects.create(name='Рис', unit='г')
        cls.ing2 = Ingredient.objects.create(name='Соль', unit='г')

    def _payload(self, **overrides):
        data = {
            'name': 'Плов',
            'text': 'Описание',
            'cooking_time': 60,
            'image': base64_image(),
            'tags': [self.tag.id],
            'ingredients': [{'id': self.ing1.id, 'amount': 100}],
        }
        data.update(overrides)
        return data

    def _serializer(self, data):
        return RecipeCreateUpdateSerializer(
            data=data, context={'request': make_request(self.author)})

    def test_empty_ingredients_invalid(self):
        serializer = self._serializer(self._payload(ingredients=[]))
        self.assertFalse(serializer.is_valid())
        self.assertIn('ingredients', serializer.errors)

    def test_duplicate_ingredients_invalid(self):
        serializer = self._serializer(self._payload(ingredients=[
            {'id': self.ing1.id, 'amount': 100},
            {'id': self.ing1.id, 'amount': 50},
        ]))
        self.assertFalse(serializer.is_valid())
        self.assertIn('ingredients', serializer.errors)

    def test_empty_tags_invalid(self):
        serializer = self._serializer(self._payload(tags=[]))
        self.assertFalse(serializer.is_valid())
        self.assertIn('tags', serializer.errors)

    def test_duplicate_tags_invalid(self):
        serializer = self._serializer(
            self._payload(tags=[self.tag.id, self.tag.id]))
        self.assertFalse(serializer.is_valid())
        self.assertIn('tags', serializer.errors)

    def test_amount_below_min_invalid(self):
        serializer = self._serializer(self._payload(
            ingredients=[{'id': self.ing1.id, 'amount': 0}]))
        self.assertFalse(serializer.is_valid())
        self.assertIn('ingredients', serializer.errors)

    def test_amount_above_max_invalid(self):
        serializer = self._serializer(self._payload(
            ingredients=[{'id': self.ing1.id, 'amount': 5001}]))
        self.assertFalse(serializer.is_valid())
        self.assertIn('ingredients', serializer.errors)

    def test_create(self):
        serializer = self._serializer(self._payload())
        self.assertTrue(serializer.is_valid(), serializer.errors)
        recipe = serializer.save()
        self.assertEqual(recipe.author, self.author)
        self.assertEqual(recipe.tags.count(), 1)
        self.assertEqual(recipe.recipeingredient_set.count(), 1)
        link = recipe.recipeingredient_set.first()
        self.assertEqual(link.ingredient, self.ing1)
        self.assertEqual(link.amount, 100)

    def test_update_replaces_ingredients_and_tags(self):
        serializer = self._serializer(self._payload())
        serializer.is_valid(raise_exception=True)
        recipe = serializer.save()
        new_data = self._payload(
            name='Плов 2',
            tags=[self.tag2.id],
            ingredients=[{'id': self.ing2.id, 'amount': 7}],
        )
        update_serializer = RecipeCreateUpdateSerializer(
            instance=recipe, data=new_data,
            context={'request': make_request(self.author)})
        update_serializer.is_valid(raise_exception=True)
        updated = update_serializer.save()
        self.assertEqual(updated.recipeingredient_set.count(), 1)
        link = updated.recipeingredient_set.first()
        self.assertEqual(link.ingredient, self.ing2)
        self.assertEqual(list(updated.tags.all()), [self.tag2])

    def test_to_representation_uses_full_serializer(self):
        serializer = self._serializer(self._payload())
        serializer.is_valid(raise_exception=True)
        serializer.save()
        data = serializer.data
        self.assertIn('is_favorited', data)
        self.assertIn('is_in_shopping_cart', data)
        self.assertIsInstance(data['tags'], list)
        self.assertEqual(data['tags'][0]['slug'], 'lunch')


class TagSerializerTest(TestCase):
    """M6: корректные fields/read_only_fields."""

    @classmethod
    def setUpTestData(cls):
        cls.tag = Tag.objects.create(
            name='Завтрак', color='#AA0000', slug='breakfast')

    def test_fields(self):
        data = TagSerializer(self.tag).data
        self.assertEqual(
            set(data.keys()), {'id', 'name', 'color', 'slug'})
        self.assertEqual(data['slug'], 'breakfast')

    def test_read_only_fields(self):
        self.assertEqual(
            TagSerializer.Meta.read_only_fields,
            ('id', 'name', 'color', 'slug'))


@override_settings(MEDIA_ROOT=TEMP_MEDIA_ROOT)
class FavoriteAndShoppingSerializerTest(TestCase):
    """M5: write_only user/recipe, валидация повтора, to_representation."""

    @classmethod
    def setUpTestData(cls):
        cls.user = create_user('1')
        cls.recipe = create_recipe(cls.user)

    def test_write_only_fields(self):
        for serializer_cls in (
            FavoriteRecipeSerializer, RecipeShoppingListSerializer
        ):
            serializer = serializer_cls()
            self.assertTrue(serializer.fields['user'].write_only)
            self.assertTrue(serializer.fields['recipe'].write_only)

    def test_favorite_duplicate_invalid(self):
        FavoriteRecipe.objects.create(user=self.user, recipe=self.recipe)
        serializer = FavoriteRecipeSerializer(
            data={'user': self.user.id, 'recipe': self.recipe.id})
        self.assertFalse(serializer.is_valid())

    def test_shopping_duplicate_invalid(self):
        RecipeShoppingList.objects.create(user=self.user, recipe=self.recipe)
        serializer = RecipeShoppingListSerializer(
            data={'user': self.user.id, 'recipe': self.recipe.id})
        self.assertFalse(serializer.is_valid())

    def test_favorite_to_representation_is_full_recipe(self):
        favorite = FavoriteRecipe.objects.create(
            user=self.user, recipe=self.recipe)
        data = FavoriteRecipeSerializer(
            favorite, context={'request': make_request(self.user)}).data
        self.assertIn('is_favorited', data)
        self.assertEqual(data['id'], self.recipe.id)

    def test_shopping_to_representation_is_short_recipe(self):
        shopping = RecipeShoppingList.objects.create(
            user=self.user, recipe=self.recipe)
        data = RecipeShoppingListSerializer(
            shopping, context={'request': make_request(self.user)}).data
        self.assertEqual(
            set(data.keys()), {'id', 'name', 'image', 'cooking_time'})


@override_settings(MEDIA_ROOT=TEMP_MEDIA_ROOT)
class SubscriptionsSerializerTest(TestCase):
    """C11/L2: recipes, recipes_limit, recipes_count, is_subscribed=True."""

    @classmethod
    def setUpTestData(cls):
        cls.author = create_user('1')
        cls.subscriber = create_user('2')
        for i in range(3):
            create_recipe(cls.author, name=f'Рецепт {i}')

    def test_is_subscribed_always_true(self):
        data = SubscriptionsSerializer(
            self.author,
            context={'request': make_request(self.subscriber)}).data
        self.assertTrue(data['is_subscribed'])

    def test_recipes_count_and_list(self):
        data = SubscriptionsSerializer(
            self.author,
            context={'request': make_request(self.subscriber)}).data
        self.assertEqual(data['recipes_count'], 3)
        self.assertEqual(len(data['recipes']), 3)

    def test_recipes_limit_applied(self):
        request = make_request(self.subscriber, query='recipes_limit=2')
        data = SubscriptionsSerializer(
            self.author, context={'request': request}).data
        self.assertEqual(len(data['recipes']), 2)
        self.assertEqual(data['recipes_count'], 3)
