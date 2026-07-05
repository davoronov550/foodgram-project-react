"""Тесты фильтров приложения api (api/filters.py)."""
import shutil
import tempfile

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.core.files.uploadedfile import SimpleUploadedFile
from django.http import QueryDict
from django.test import RequestFactory, TestCase, override_settings
from rest_framework.test import APITestCase

from api.filters import RecipeFilter
from recipes.models import (
    FavoriteRecipe,
    Ingredient,
    Recipe,
    RecipeShoppingList,
    Tag,
)

User = get_user_model()

TEMP_MEDIA_ROOT = tempfile.mkdtemp()

SMALL_GIF = (
    b'\x47\x49\x46\x38\x39\x61\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00'
    b'\xff\xff\xff\x21\xf9\x04\x00\x00\x00\x00\x00\x2c\x00\x00\x00\x00'
    b'\x01\x00\x01\x00\x00\x02\x02\x4c\x01\x00\x3b'
)


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


def create_recipe(author, name='Рецепт'):
    return Recipe.objects.create(
        author=author,
        name=name,
        image=image_file(f'{name}.gif'),
        text='Описание',
        cooking_time=30,
    )


def build_query(data):
    """Строит QueryDict, корректно раскладывая списочные значения."""
    qd = QueryDict(mutable=True)
    for key, value in data.items():
        if isinstance(value, (list, tuple)):
            qd.setlist(key, [str(item) for item in value])
        else:
            qd[key] = str(value)
    return qd


def tearDownModule():
    shutil.rmtree(TEMP_MEDIA_ROOT, ignore_errors=True)


@override_settings(MEDIA_ROOT=TEMP_MEDIA_ROOT)
class RecipeFilterTest(TestCase):
    """RecipeFilter: author, tags, is_favorited, is_in_shopping_cart."""

    @classmethod
    def setUpTestData(cls):
        cls.user = create_user('1')
        cls.author1 = create_user('2')
        cls.author2 = create_user('3')
        cls.lunch = Tag.objects.create(
            name='Обед', color='#0000AA', slug='lunch')
        cls.dinner = Tag.objects.create(
            name='Ужин', color='#00AA00', slug='dinner')
        cls.breakfast = Tag.objects.create(
            name='Завтрак', color='#AA0000', slug='breakfast')

        cls.r1 = create_recipe(cls.author1, name='Рецепт 1')
        cls.r1.tags.add(cls.lunch)
        cls.r2 = create_recipe(cls.author1, name='Рецепт 2')
        cls.r2.tags.add(cls.dinner)
        cls.r3 = create_recipe(cls.author2, name='Рецепт 3')
        cls.r3.tags.add(cls.breakfast)

    def _filter(self, data, user=None):
        request = RequestFactory().get('/')
        request.user = user if user is not None else AnonymousUser()
        filterset = RecipeFilter(
            build_query(data),
            queryset=Recipe.objects.all(),
            request=request,
        )
        return filterset.qs

    def test_filter_by_single_author(self):
        qs = self._filter({'author': [self.author1.id]})
        self.assertCountEqual(qs, [self.r1, self.r2])

    def test_filter_by_multiple_authors(self):
        qs = self._filter({'author': [self.author1.id, self.author2.id]})
        self.assertCountEqual(qs, [self.r1, self.r2, self.r3])

    def test_filter_by_single_tag_slug(self):
        qs = self._filter({'tags': ['lunch']})
        self.assertCountEqual(qs, [self.r1])

    def test_filter_by_multiple_tag_slugs(self):
        qs = self._filter({'tags': ['lunch', 'dinner']})
        self.assertCountEqual(qs, [self.r1, self.r2])

    def test_is_favorited_true(self):
        FavoriteRecipe.objects.create(user=self.user, recipe=self.r1)
        qs = self._filter({'is_favorited': 'true'}, user=self.user)
        self.assertCountEqual(qs, [self.r1])

    def test_is_favorited_false(self):
        FavoriteRecipe.objects.create(user=self.user, recipe=self.r1)
        qs = self._filter({'is_favorited': 'false'}, user=self.user)
        self.assertCountEqual(qs, [self.r2, self.r3])

    def test_is_favorited_distinct_with_tags(self):
        """H11: рецепт с несколькими подходящими тегами не дублируется."""
        self.r1.tags.add(self.dinner)
        FavoriteRecipe.objects.create(user=self.user, recipe=self.r1)
        qs = self._filter(
            {'tags': ['lunch', 'dinner'], 'is_favorited': 'true'},
            user=self.user,
        )
        self.assertEqual(qs.count(), 1)
        self.assertEqual(list(qs), [self.r1])

    def test_is_favorited_true_anonymous_returns_empty(self):
        """Аноним: is_favorited=true не падает и отдаёт пустой результат."""
        FavoriteRecipe.objects.create(user=self.user, recipe=self.r1)
        qs = self._filter({'is_favorited': 'true'})
        self.assertEqual(list(qs), [])

    def test_is_favorited_false_anonymous_returns_all(self):
        """Аноним: is_favorited=false не падает и отдаёт все рецепты."""
        FavoriteRecipe.objects.create(user=self.user, recipe=self.r1)
        qs = self._filter({'is_favorited': 'false'})
        self.assertCountEqual(qs, [self.r1, self.r2, self.r3])

    def test_is_in_shopping_cart_true(self):
        RecipeShoppingList.objects.create(user=self.user, recipe=self.r1)
        qs = self._filter({'is_in_shopping_cart': 'true'}, user=self.user)
        self.assertCountEqual(qs, [self.r1])

    def test_is_in_shopping_cart_true_anonymous_returns_empty(self):
        """Аноним: is_in_shopping_cart=true не падает, результат пуст."""
        RecipeShoppingList.objects.create(user=self.user, recipe=self.r1)
        qs = self._filter({'is_in_shopping_cart': 'true'})
        self.assertEqual(list(qs), [])

    def test_is_in_shopping_cart_false_anonymous_returns_all(self):
        """Аноним: is_in_shopping_cart=false не падает, отдаёт все."""
        RecipeShoppingList.objects.create(user=self.user, recipe=self.r1)
        qs = self._filter({'is_in_shopping_cart': 'false'})
        self.assertCountEqual(qs, [self.r1, self.r2, self.r3])

    def test_is_in_shopping_cart_false_preserves_other_filters(self):
        """C3: False-ветка не падает и сохраняет фильтр по автору."""
        RecipeShoppingList.objects.create(user=self.user, recipe=self.r1)
        qs = self._filter(
            {'author': [self.author1.id], 'is_in_shopping_cart': 'false'},
            user=self.user,
        )
        self.assertCountEqual(qs, [self.r2])

    def test_combined_author_and_tag(self):
        qs = self._filter(
            {'author': [self.author1.id], 'tags': ['dinner']})
        self.assertCountEqual(qs, [self.r2])

    def test_no_filters_returns_all(self):
        qs = self._filter({})
        self.assertCountEqual(qs, [self.r1, self.r2, self.r3])


class IngredientFilterTest(APITestCase):
    """IngredientFilter: поиск по префиксу ^name через эндпоинт."""

    @classmethod
    def setUpTestData(cls):
        cls.sugar = Ingredient.objects.create(name='Сахар', unit='г')
        cls.salt = Ingredient.objects.create(name='Соль', unit='г')
        cls.sand = Ingredient.objects.create(name='Сахарная пудра', unit='г')
        cls.rice = Ingredient.objects.create(name='Рис', unit='г')

    def test_prefix_match(self):
        response = self.client.get('/api/ingredients/?name=Сах')
        names = {item['name'] for item in response.data}
        self.assertEqual(names, {'Сахар', 'Сахарная пудра'})

    def test_prefix_does_not_match_substring(self):
        """^name — совпадение только с начала строки."""
        response = self.client.get('/api/ingredients/?name=ахар')
        self.assertEqual(response.data, [])

    def test_case_insensitive(self):
        response = self.client.get('/api/ingredients/?name=сах')
        names = {item['name'] for item in response.data}
        self.assertEqual(names, {'Сахар', 'Сахарная пудра'})

    def test_empty_query_returns_all(self):
        response = self.client.get('/api/ingredients/')
        self.assertEqual(len(response.data), 4)
