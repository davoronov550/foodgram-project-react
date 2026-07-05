"""Тесты моделей приложений recipes и users."""
import shutil
import tempfile
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from django.utils import timezone

from recipes.models import (
    FavoriteRecipe,
    Ingredient,
    Recipe,
    RecipeIngredient,
    RecipeShoppingList,
    RecipeTag,
    Tag,
)
from users.models import Follow

User = get_user_model()

TEMP_MEDIA_ROOT = tempfile.mkdtemp()

# Минимальный валидный 1x1 GIF для ImageField.
SMALL_GIF = (
    b'\x47\x49\x46\x38\x39\x61\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00'
    b'\xff\xff\xff\x21\xf9\x04\x00\x00\x00\x00\x00\x2c\x00\x00\x00\x00'
    b'\x01\x00\x01\x00\x00\x02\x02\x4c\x01\x00\x3b'
)


def image_file(name='test.gif'):
    """Возвращает загружаемый файл-картинку для рецепта."""
    return SimpleUploadedFile(name, SMALL_GIF, content_type='image/gif')


def create_user(suffix='1'):
    """Создаёт пользователя с уникальными email/username."""
    return User.objects.create_user(
        username=f'user{suffix}',
        email=f'user{suffix}@example.com',
        password='Pass!2345',
        first_name='Имя',
        last_name='Фамилия',
    )


def tearDownModule():
    """Удаляет временный каталог медиа после всех тестов модуля."""
    shutil.rmtree(TEMP_MEDIA_ROOT, ignore_errors=True)


class UserModelTest(TestCase):
    """Тесты модели User."""

    @classmethod
    def setUpTestData(cls):
        cls.user = create_user('1')

    def test_username_field_is_email(self):
        self.assertEqual(User.USERNAME_FIELD, 'email')

    def test_required_fields(self):
        self.assertIn('username', User.REQUIRED_FIELDS)

    def test_str_returns_username(self):
        self.assertEqual(str(self.user), self.user.username)

    def test_unique_user_constraint_declared(self):
        names = {c.name for c in User._meta.constraints}
        self.assertIn('unique_user', names)

    def test_email_must_be_unique(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                User.objects.create_user(
                    username='other',
                    email='user1@example.com',
                    password='Pass!2345',
                )

    def test_username_must_be_unique(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                User.objects.create_user(
                    username='user1',
                    email='other@example.com',
                    password='Pass!2345',
                )


class FollowModelTest(TestCase):
    """Тесты модели Follow."""

    @classmethod
    def setUpTestData(cls):
        cls.user = create_user('1')
        cls.author = create_user('2')

    def test_str(self):
        follow = Follow.objects.create(user=self.user, author=self.author)
        self.assertEqual(
            str(follow),
            f'Пользователь {self.user} подписан(а) на {self.author}',
        )

    def test_unique_follow(self):
        Follow.objects.create(user=self.user, author=self.author)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Follow.objects.create(user=self.user, author=self.author)

    def test_no_self_follow(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Follow.objects.create(user=self.user, author=self.user)

    def test_no_self_follow_constraint_declared(self):
        names = {c.name for c in Follow._meta.constraints}
        self.assertIn('no_self_follow', names)
        self.assertIn('unique_follow', names)


class TagModelTest(TestCase):
    """Тесты модели Tag."""

    @classmethod
    def setUpTestData(cls):
        cls.tag = Tag.objects.create(
            name='Завтрак', color='#AA0000', slug='breakfast',
        )

    def test_str_returns_name(self):
        self.assertEqual(str(self.tag), 'Завтрак')

    def test_name_unique(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Tag.objects.create(
                    name='Завтрак', color='#BB0000', slug='other',
                )

    def test_color_unique(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Tag.objects.create(
                    name='Обед', color='#AA0000', slug='lunch',
                )

    def test_slug_unique(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Tag.objects.create(
                    name='Ужин', color='#CC0000', slug='breakfast',
                )

    def test_no_redundant_unique_tags_constraint(self):
        names = {c.name for c in Tag._meta.constraints}
        self.assertNotIn('unique_tags', names)


class IngredientModelTest(TestCase):
    """Тесты модели Ingredient."""

    @classmethod
    def setUpTestData(cls):
        cls.ingredient = Ingredient.objects.create(name='Соль', unit='г')

    def test_str(self):
        self.assertEqual(str(self.ingredient), 'Соль г')

    def test_unit_field_present(self):
        self.assertEqual(self.ingredient.unit, 'г')

    def test_unique_name_unit(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Ingredient.objects.create(name='Соль', unit='г')

    def test_same_name_other_unit_allowed(self):
        Ingredient.objects.create(name='Соль', unit='кг')
        self.assertEqual(Ingredient.objects.filter(name='Соль').count(), 2)


@override_settings(MEDIA_ROOT=TEMP_MEDIA_ROOT)
class RecipeModelTest(TestCase):
    """Тесты модели Recipe."""

    @classmethod
    def setUpTestData(cls):
        cls.author = create_user('1')
        cls.recipe = Recipe.objects.create(
            author=cls.author,
            name='Борщ',
            image=image_file('borsch.gif'),
            text='Описание',
            cooking_time=60,
        )

    def test_str_returns_name(self):
        self.assertEqual(str(self.recipe), 'Борщ')

    def test_default_ordering_is_newest_first(self):
        older = Recipe.objects.create(
            author=self.author,
            name='Старый рецепт',
            image=image_file('old.gif'),
            text='Описание',
            cooking_time=10,
        )
        Recipe.objects.filter(pk=older.pk).update(
            pub_date=timezone.now() - timedelta(days=1)
        )
        self.assertEqual(list(Recipe.objects.all()), [self.recipe, older])

    def test_pub_date_index_declared(self):
        names = {index.name for index in Recipe._meta.indexes}
        self.assertIn('recipe_pub_date_idx', names)

    def test_unique_recipe_per_author(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Recipe.objects.create(
                    author=self.author,
                    name='Борщ',
                    image=image_file('dup.gif'),
                    text='Другое описание',
                    cooking_time=30,
                )

    def test_same_name_other_author_allowed(self):
        other_author = create_user('2')
        Recipe.objects.create(
            author=other_author,
            name='Борщ',
            image=image_file('borsch2.gif'),
            text='Описание',
            cooking_time=45,
        )
        self.assertEqual(Recipe.objects.filter(name='Борщ').count(), 2)

    def test_cooking_time_min_boundary(self):
        recipe = Recipe(
            author=self.author,
            name='Минимум',
            image=image_file('min.gif'),
            text='t',
            cooking_time=0,
        )
        with self.assertRaises(ValidationError):
            recipe.full_clean()

    def test_cooking_time_max_boundary(self):
        recipe = Recipe(
            author=self.author,
            name='Максимум',
            image=image_file('max.gif'),
            text='t',
            cooking_time=481,
        )
        with self.assertRaises(ValidationError):
            recipe.full_clean()

    def test_cooking_time_valid_boundaries(self):
        for value in (1, 480):
            recipe = Recipe(
                author=self.author,
                name=f'Рецепт {value}',
                image=image_file(f'ok{value}.gif'),
                text='t',
                cooking_time=value,
            )
            recipe.full_clean()  # не должно бросать ValidationError


@override_settings(MEDIA_ROOT=TEMP_MEDIA_ROOT)
class RecipeRelationsModelTest(TestCase):
    """Тесты связующих моделей и списков (избранное/покупки)."""

    @classmethod
    def setUpTestData(cls):
        cls.user = create_user('1')
        cls.recipe = Recipe.objects.create(
            author=cls.user,
            name='Плов',
            image=image_file('plov.gif'),
            text='Описание',
            cooking_time=90,
        )
        cls.ingredient = Ingredient.objects.create(name='Рис', unit='г')
        cls.tag = Tag.objects.create(
            name='Обед', color='#0000AA', slug='lunch',
        )

    # --- RecipeIngredient ---
    def test_recipe_ingredient_str(self):
        link = RecipeIngredient.objects.create(
            recipe=self.recipe, ingredient=self.ingredient, amount=200,
        )
        self.assertEqual(
            str(link),
            f'Ингредиент {self.ingredient.name} в рецепте {self.recipe} - '
            f'200 {self.ingredient.unit}',
        )

    def test_recipe_ingredient_unique(self):
        RecipeIngredient.objects.create(
            recipe=self.recipe, ingredient=self.ingredient, amount=200,
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                RecipeIngredient.objects.create(
                    recipe=self.recipe, ingredient=self.ingredient, amount=5,
                )

    def test_amount_min_boundary(self):
        link = RecipeIngredient(
            recipe=self.recipe, ingredient=self.ingredient, amount=0,
        )
        with self.assertRaises(ValidationError):
            link.full_clean()

    def test_amount_max_boundary(self):
        link = RecipeIngredient(
            recipe=self.recipe, ingredient=self.ingredient, amount=5001,
        )
        with self.assertRaises(ValidationError):
            link.full_clean()

    def test_amount_valid_boundaries(self):
        for value in (1, 5000):
            ingredient = Ingredient.objects.create(
                name=f'Ингр {value}', unit='г',
            )
            link = RecipeIngredient(
                recipe=self.recipe, ingredient=ingredient, amount=value,
            )
            link.full_clean()  # не должно бросать ValidationError

    # --- RecipeTag ---
    def test_recipe_tag_str(self):
        link = RecipeTag.objects.create(recipe=self.recipe, tag=self.tag)
        self.assertEqual(
            str(link), f'Тег {self.tag} в рецепте {self.recipe}',
        )

    def test_recipe_tag_unique(self):
        RecipeTag.objects.create(recipe=self.recipe, tag=self.tag)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                RecipeTag.objects.create(recipe=self.recipe, tag=self.tag)

    # --- FavoriteRecipe ---
    def test_favorite_str(self):
        favorite = FavoriteRecipe.objects.create(
            user=self.user, recipe=self.recipe,
        )
        self.assertEqual(
            str(favorite),
            f'Рецепт {self.recipe} в избранном списке '
            f'пользователя {self.user}',
        )

    def test_favorite_unique(self):
        FavoriteRecipe.objects.create(user=self.user, recipe=self.recipe)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                FavoriteRecipe.objects.create(
                    user=self.user, recipe=self.recipe,
                )

    # --- RecipeShoppingList ---
    def test_shopping_str(self):
        shopping = RecipeShoppingList.objects.create(
            user=self.user, recipe=self.recipe,
        )
        self.assertEqual(
            str(shopping),
            f'У пользователя {self.user} рецепт {self.recipe} '
            f'в списке покупок',
        )

    def test_shopping_unique(self):
        RecipeShoppingList.objects.create(user=self.user, recipe=self.recipe)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                RecipeShoppingList.objects.create(
                    user=self.user, recipe=self.recipe,
                )
