# Ревью бэкенда Foodgram — отчёт

Дата: 2026-06-11
Объём: полное ревью бэкенда (корректность/DRF, безопасность, БД/производительность, тесты).
Статус: **BLOCK** — найдено множество CRITICAL/HIGH багов, ломающих основную функциональность
и безопасность. Код в рамках этого этапа **не изменялся** — только отчёт.

Стек: Django 4.2.3, DRF 3.14, Djoser 2.2, TokenAuthentication, PostgreSQL.
Фронтенд (React 17) не редактируется — он задаёт API-контракт.

---

## 1. Применённые плагины / агенты / навыки (Задача 4)

### Агенты, реально запущенные для этого ревью
| Агент | Зона | Результат |
|-------|------|-----------|
| **python-reviewer** | Корректность, DRF/Django-идиомы, соответствие контракту | 6 CRITICAL, 6 HIGH, 7 MEDIUM/LOW |
| **security-reviewer** | OWASP, секреты, настройки, права | 4 CRITICAL, 5 HIGH, 5 MEDIUM, 3 LOW |
| **database-reviewer** | N+1, индексы, агрегации, схема | 3 CRITICAL, 3 HIGH, 3 MEDIUM/LOW |
| (ручной анализ) | Тесты (`api/tests.py`) | покрытие ~1% |

### Дополнительно доступные для углубления
- Агенты: `performance-optimizer`, `code-reviewer`, `silent-failure-hunter`,
  `pr-test-analyzer`, `tdd-guide`, `type-design-analyzer`.
- Навыки (Skill): `django-patterns`, `django-security`, `django-tdd`, `django-verification`,
  `python-patterns`, `python-testing`, `postgres-patterns`, `api-design`, `backend-patterns`.
- Команды: `/python-review`, `/security-review`, `/code-review`, `/test-coverage`.
  (`/code-review ultra` — многоагентное облачное ревью — запускается пользователем.)

---

## 2. Баги, объясняющие «неработающие кнопки» (приоритет для исправления)

Это находки, напрямую ломающие UI-действия:

| Симптом в UI | Корень в бэкенде | Файл |
|--------------|------------------|------|
| Единица измерения ингредиента не отображается нигде; автоподстановка в форме рецепта пустая | Бэкенд отдаёт поле `unit`, фронт читает `measurement_unit` | `api/serializers.py:82-93`, `recipes/models.py:48` |
| Ссылки на рецепты в «Моих подписках» ведут на `/recipes/undefined` | `RecipeShortSerializer` не отдаёт `id` (и лишний `author`) | `api/serializers.py:96-105` |
| Фильтр «в списке покупок» (и комбинированные фильтры) роняет список рецептов в 500 | `get_is_in_shopping_cart` возвращает `None` при `value=False` и сбрасывает прочие фильтры | `api/filters.py:57-62` |
| DELETE из избранного/корзины несуществующего рецепта → 500 | `Response({'...'})` — это `set`, не сериализуется в JSON | `api/views.py:149` |
| Смена пароля «работает», но без проверки текущего | `set_password` игнорирует `current_password` | `api/views.py:38-53` |
| Скачивание списка покупок: имя файла `shopping_list.txt.txt`; доступно без авторизации | двойное расширение + `AuthorOnly` на `detail=False` | `api/views.py:166-179` |
| Создание рецепта с дублем ингредиента → 500 | нет проверки дублей в `validate_ingredients` | `api/serializers.py:180-186` |
| Создание рецепта с `amount<=0` проходит | `IntegerField()` без `min_value` | `api/serializers.py:154` |

---

## 3. CRITICAL

### C1. Несоответствие контракта: `unit` vs `measurement_unit`
`recipes/models.py:48` — поле модели `unit`; `IngredientSerializer` (`__all__`) и
`RecipeIngredientSerializer` (`api/serializers.py:82-93`) отдают `unit`. Фронт повсеместно
читает `measurement_unit` (`frontend/src/pages/single-card/ingredients/index.js:11`,
`recipe-create/index.js`, `components/ingredients-search/index.js:5`).
**Fix:** `measurement_unit = serializers.ReadOnlyField(source='ingredient.unit')`;
в `IngredientSerializer` отдавать поле как `measurement_unit` (явный список полей).

### C2. `RecipeShortSerializer` без `id`
`api/serializers.py:96-105` — `fields = ('name','image','author','cooking_time')`.
Компонент подписок (`frontend/src/components/subscription/index.js:25-26`) использует
`recipe.id`. **Fix:** `fields = ('id','name','image','cooking_time')`.

### C3. `get_is_in_shopping_cart` возвращает `None` + сбрасывает фильтры
`api/filters.py:57-62`. **Fix:**
```python
def get_is_in_shopping_cart(self, queryset, name, value):
    if value:
        return queryset.filter(shopping__user=self.request.user).distinct()
    return queryset.exclude(shopping__user=self.request.user).distinct()
```

### C4. `download_shopping_cart` доступен без авторизации
`api/views.py:166` + `api/permissions.py:4-11`. `AuthorOnly` реализует только
`has_object_permission`, для `detail=False` он не вызывается → `has_permission` по умолчанию
`True`. При `DEFAULT_PERMISSION_CLASSES = AllowAny` эндпоинт открыт анонимам.
**Fix:** `permission_classes=[permissions.IsAuthenticated]`.

### C5. `Response({'...'})` — set вместо dict → 500
`api/views.py:149`. **Fix:** `Response({'error': 'Этого рецепта не было в списке'}, status=400)`.

### C6. `set_password` не проверяет `current_password`
`api/views.py:38-53` — захват аккаунта при утечке токена; перекрывает корректный
эндпоинт Djoser. **Fix:** проверять `request.user.check_password(current_password)`,
использовать `user.set_password(...)`, либо удалить кастомный action и положиться на Djoser.

### C7. Mass-assignment при регистрации (`fields = ('__all__')`)
`api/serializers.py:22-23` — `('__all__')` это строка `'__all__'`, DRF раскрывает в все поля
`AbstractUser`, включая `is_staff`/`is_superuser`/`is_active`. POST `/api/users/` может создать
суперпользователя. **Fix:** явный список `('email','id','username','first_name','last_name','password')`,
`extra_kwargs={'password':{'write_only':True}}`.

### C8. Реальный `SECRET_KEY` и пароль БД в истории git
Каталог `.history/` (VSCode Local History) закоммичен с секретами: в `ebbab14`
`.history/.env_20230828131130` содержит `TOKEN='django-insecure-...'` и `POSTGRES_PASSWORD`.
В истории ~313 blob-ов `.env`. **Fix:** срочно **ротировать** `SECRET_KEY` и пароль БД в
проде; добавить `.history/` в `.gitignore`; рассмотреть очистку истории
(`git filter-repo`) и форс-пуш по согласованию.

### C9 (perf). N+1 в списке рецептов
`api/views.py:108` + `api/serializers.py:113-119`: нет `select_related/prefetch_related`;
`author`, `tags`, `recipeingredient_set→ingredient` тянутся по запросу на рецепт.
**Fix:** `get_queryset` с
`select_related('author').prefetch_related('tags', Prefetch('recipeingredient_set', queryset=RecipeIngredient.objects.select_related('ingredient')))`.

### C10 (perf). N+1 в `is_favorited`/`is_in_shopping_cart`
`api/serializers.py:130-144` — запрос на каждый рецепт. **Fix:** аннотировать
`Exists(...)` на queryset, поля заменить на `BooleanField(read_only=True)`.

### C11 (perf). N+1 в подписках
`api/views.py:91-93` + `api/serializers.py:247-261`: нет `prefetch_related('recipes')`,
`get_recipes_count` делает `.count()` на автора, срез `recipes.all()[:limit]` обходит кэш,
`get_is_subscribed` — запрос на автора. **Fix:** `prefetch_related('recipes')`, `len()` по
кэшу, срез в Python, `get_is_subscribed → True` в `SubscriptionsSerializer`.

---

## 4. HIGH

| # | Файл | Проблема | Fix |
|---|------|----------|-----|
| H1 | `recipebook/settings.py:12` | `DEBUG = True` хардкод на боевом IP | `DEBUG = os.getenv('DEBUG','False')=='True'` |
| H2 | `recipebook/settings.py:19-21` | Нет запятой → склейка строк, `127.0.0.1` выпадает из `CSRF_TRUSTED_ORIGINS` | добавить запятую |
| H3 | `recipebook/settings.py:10` | Слабый fallback `'default-token'`, странное имя env `TOKEN` | `os.environ['DJANGO_SECRET_KEY']` без fallback |
| H4 | `recipebook/settings.py:88` | Дефолт пароля БД `'postgres'` | убрать дефолт |
| H5 | `infra/nginx.conf` | Нет TLS — токены по HTTP | настроить HTTPS + `SECURE_*`/`*_COOKIE_SECURE` |
| H6 | `api/views.py:114-121` | CRUD рецепта без проверки автора — любой авторизованный может PATCH/DELETE чужой рецепт | `get_permissions` → `[IsAuthenticated, AuthorOnly]` для update/partial_update/destroy |
| H7 | `api/serializers.py:154` | `amount` без `min_value`/`max_value` | `IntegerField(min_value=1, max_value=5000)` |
| H8 | `api/serializers.py:180-186` | нет проверки дублей ингредиентов → IntegrityError 500 | проверка `len != len(set)` |
| H9 | `api/serializers.py:167-170` | нет `validate_tags` (пустые/дубли) | добавить `validate_tags` |
| H10 | `api/views.py:178` | имя файла `shopping_list.txt.txt` | `file='shopping_list'` |
| H11 | `api/filters.py:47-55` | join без `.distinct()` → дубли рецептов, ломает пагинацию | `.distinct()` на все ветки |
| H12 | `recipes/models.py:115` | нет индекса под `ordering=('-pub_date',)` | `indexes=[Index(fields=['-pub_date'])]` |
| H13 | `api/services.py:11-16` | `values_list` по сырым путям после алиасов `values()` — Sum может «потеряться» | использовать алиасы `('name','unit','total')` |

---

## 5. MEDIUM / LOW

- M1 `api/serializers.py:264-292` — `FollowSerializer` мёртвый и содержит `KeyError`
  (`data['following']` при поле `author`); нигде не используется. Удалить или починить.
- M2 `recipebook/settings.py:48-57` — `CorsMiddleware` ниже `SessionMiddleware`; должен быть выше.
- M3 `recipebook/settings.py:142-145` — `DEFAULT_PERMISSION_CLASSES = AllowAny`; безопаснее
  `IsAuthenticated` по умолчанию + явные исключения.
- M4 `recipebook/settings.py:23` — `CORS_ORIGIN_ALLOW_ALL = True`; задать allowlist.
- M5 `api/serializers.py:333-341` — `RecipeShoppingListSerializer` без `write_only` на user/recipe
  (несогласованно с `FavoriteRecipeSerializer`).
- M6 `api/serializers.py:62,71` — `fields = ('__all__')` и `read_only_fields = (fields,)` —
  строка вместо tuple; read-only по факту не применяется.
- M7 `users/models.py:30-34` — кастомный `password max_length=150`; лучше не переопределять
  (Django: 128), иначе риск усечения для argon2/scrypt.
- M8 `recipes/models.py:75-79` — `Recipe.name unique=True` глобально (два юзера не могут иметь
  одноимённый рецепт); заменить на `UniqueConstraint(('author','name'))` либо убрать.
- L1 `recipes/models.py:26-35` — `Tag` `UniqueConstraint(name,color)` избыточен (оба поля уже unique).
- L2 `api/serializers.py:50-55` — `get_is_subscribed` лишний запрос на автора в списке подписок.
- L3 `backend/Dockerfile` — контейнер от root; нет `USER`. Базовый образ `python:3.9` без digest.
- L4 `.github/workflows/main.yml` — actions `appleboy/*@master` (нестабильный пин).
- L5 Везде — нет type-аннотаций и логирования.

---

## 6. Тесты

`api/tests.py` — единственный активный тест `test_list_exists` (GET `/api/recipes/` → 200);
остальные закомментированы (в т.ч. с опечаткой URL `/api/pecipe/`). Покрытие ~1%.
Фреймворк — `django.test` (в зависимостях нет pytest, есть только flake8).

**Рекомендация:** добавить тесты на:
регистрацию (и запрет mass-assignment is_staff), auth-token login,
CRUD рецепта + права автора, favorite/shopping_cart (POST/DELETE, повтор, отсутствие),
subscribe/unsubscribe + запрет на себя, фильтры (tags/author/is_favorited/is_in_shopping_cart),
download_shopping_cart (только авторизованный, корректная агрегация),
смену пароля с проверкой current_password. Цель — 80%+.

---

## 7. Приоритетный план исправлений (для следующего этапа)

**Шаг 1 — безопасность (срочно):** C8 (ротация ключа/пароля, `.history/` в .gitignore),
C7, C6, C4, H1, H2, H3, H4.
**Шаг 2 — «неработающие кнопки»:** C1, C2, C3, C5, H6, H7, H8, H9, H10.
**Шаг 3 — производительность:** C9, C10, C11, H11, H12, H13.
**Шаг 4 — чистота/качество:** M1–M8, L1–L5.
**Шаг 5 — тесты:** довести покрытие до 80%+, затем регресс-прогон
(`python manage.py check`, `flake8`, тесты).
