"""Тесты сервисов приложения api (api/services.py)."""
import shutil
import tempfile

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings

from api.services import get_ingredients
from recipes.models import (
    Ingredient,
    Recipe,
    RecipeIngredient,
    RecipeShoppingList,
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


def tearDownModule():
    shutil.rmtree(TEMP_MEDIA_ROOT, ignore_errors=True)


@override_settings(MEDIA_ROOT=TEMP_MEDIA_ROOT)
class GetIngredientsTest(TestCase):
    """get_ingredients: агрегация ингредиентов корзины (H13)."""

    @classmethod
    def setUpTestData(cls):
        cls.user = create_user('1')
        cls.other = create_user('2')
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

    def test_sums_duplicate_ingredients_across_recipes(self):
        result = {row[0]: row for row in get_ingredients(self.user)}
        # Рис: 100 (Плов) + 50 (Каша) = 150
        self.assertEqual(result['Рис'][2], 150)
        self.assertEqual(result['Соль'][2], 5)

    def test_row_aliases_name_unit_total(self):
        """H13: каждая строка — кортеж (name, unit, total)."""
        rows = list(get_ingredients(self.user))
        self.assertTrue(rows)
        for row in rows:
            self.assertEqual(len(row), 3)
        rice_row = next(row for row in rows if row[0] == 'Рис')
        name, unit, total = rice_row
        self.assertEqual(name, 'Рис')
        self.assertEqual(unit, 'г')
        self.assertEqual(total, 150)

    def test_distinct_ingredients_count(self):
        rows = list(get_ingredients(self.user))
        names = [row[0] for row in rows]
        # Рис и Соль — по одной агрегированной строке на ингредиент
        self.assertEqual(len(names), 2)
        self.assertEqual(sorted(names), ['Рис', 'Соль'])

    def test_empty_cart_returns_empty(self):
        empty_user = create_user('3')
        self.assertEqual(list(get_ingredients(empty_user)), [])

    def test_isolated_per_user(self):
        """Корзина другого пользователя не влияет на агрегацию."""
        other_recipe = create_recipe(self.other, name='Суп')
        RecipeIngredient.objects.create(
            recipe=other_recipe, ingredient=self.rice, amount=999)
        RecipeShoppingList.objects.create(
            user=self.other, recipe=other_recipe)
        result = {row[0]: row for row in get_ingredients(self.user)}
        # 999 из чужой корзины не попало в сумму риса
        self.assertEqual(result['Рис'][2], 150)
