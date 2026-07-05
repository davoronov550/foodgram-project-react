# Foodgram — «Продуктовый помощник»

Foodgram — это онлайн-сервис и REST API к нему, где пользователи публикуют
рецепты, добавляют чужие рецепты в избранное, подписываются на авторов и
формируют список покупок. Перед походом в магазин список продуктов из всех
выбранных рецептов можно выгрузить одним файлом — количества одинаковых
ингредиентов при этом суммируются.

Проект состоит из бэкенда на Django REST Framework и одностраничного
фронтенда на React. В продакшене приложение работает в контейнерах
(nginx + PostgreSQL + Django/Gunicorn), сборка образов и деплой
автоматизированы через GitHub Actions.

## Возможности

Для анонимных пользователей:
- просмотр списка рецептов, отдельного рецепта, тегов и ингредиентов;
- фильтрация рецептов по тегам и авторам;
- поиск ингредиентов по началу названия;
- регистрация и получение токена авторизации.

Для авторизованных пользователей дополнительно:
- создание, редактирование и удаление **своих** рецептов (чужие защищены);
- добавление/удаление рецептов в **избранное**;
- добавление/удаление рецептов в **список покупок** и его выгрузка в `.txt`
  с суммированием повторяющихся ингредиентов;
- **подписки** на авторов и просмотр ленты подписок (с ограничением числа
  рецептов через `recipes_limit`);
- смена пароля и просмотр своего профиля (`/api/users/me/`).

Администрирование доступно через стандартную админку Django (`/admin/`).

## Технологический стек

[![Python](https://img.shields.io/badge/-Python%203.9--3.13-464646?style=flat&logo=Python&logoColor=56C0C0&color=cd5c5c)](https://www.python.org/)
[![Django](https://img.shields.io/badge/-Django%204.2-464646?style=flat&logo=Django&logoColor=56C0C0&color=0095b6)](https://www.djangoproject.com/)
[![DRF](https://img.shields.io/badge/-Django%20REST%20Framework%203.14-464646?style=flat&logo=Django&logoColor=56C0C0&color=cd5c5c)](https://www.django-rest-framework.org/)
[![PostgreSQL](https://img.shields.io/badge/-PostgreSQL%2013-464646?style=flat&logo=PostgreSQL&logoColor=56C0C0&color=0095b6)](https://www.postgresql.org/)
[![React](https://img.shields.io/badge/-React%2017-464646?style=flat&logo=React&logoColor=56C0C0&color=cd5c5c)](https://react.dev/)
[![Nginx](https://img.shields.io/badge/-NGINX-464646?style=flat&logo=NGINX&logoColor=56C0C0&color=0095b6)](https://nginx.org/ru/)
[![gunicorn](https://img.shields.io/badge/-gunicorn-464646?style=flat&logo=gunicorn&logoColor=56C0C0&color=cd5c5c)](https://gunicorn.org/)
[![Docker](https://img.shields.io/badge/-Docker-464646?style=flat&logo=Docker&logoColor=56C0C0&color=0095b6)](https://www.docker.com/)
[![GitHub Actions](https://img.shields.io/badge/-GitHub%20Actions-464646?style=flat&logo=GitHub%20actions&logoColor=56C0C0&color=cd5c5c)](https://github.com/features/actions)

| Слой | Технологии |
|------|------------|
| Backend | Python 3.9–3.13, Django 4.2, Django REST Framework 3.14, Djoser 2.2 (токен-авторизация) |
| БД | PostgreSQL 13, psycopg2-binary |
| Сервер | Gunicorn 20, Nginx 1.19 |
| Frontend | React 17 (SPA) |
| Инфраструктура | Docker, Docker Compose, GitHub Actions |
| Качество | flake8, coverage (154 теста, покрытие ~97%) |

## Структура репозитория

```
foodgram-project-react/
├── backend/            # Django-проект (API, модели, тесты)
│   ├── api/            # сериализаторы, вьюсеты, фильтры, права, сервисы, tests/
│   ├── recipes/        # модели рецептов, ингредиентов, тегов + команда import
│   ├── users/          # кастомная модель пользователя и подписки
│   ├── recipebook/     # настройки проекта
│   ├── data/           # ingredients.csv, tags.csv для наполнения БД
│   └── requirements.txt
├── frontend/           # React-приложение
├── infra/              # docker-compose.yml, nginx.conf
└── docs/               # openapi-schema.yml, redoc.html
```

## Документация API

После запуска доступна спецификация в формате ReDoc: `http://localhost:7000/api/docs/`
(исходники — `docs/openapi-schema.yml`).

Основные эндпоинты:

| Метод | Эндпоинт | Назначение |
|-------|----------|------------|
| POST | `/api/users/` | регистрация |
| POST | `/api/auth/token/login/` | получить токен |
| POST | `/api/auth/token/logout/` | удалить токен |
| GET | `/api/users/me/` | свой профиль (авторизация) |
| POST | `/api/users/set_password/` | смена пароля |
| POST/DELETE | `/api/users/{id}/subscribe/` | подписка/отписка |
| GET | `/api/users/subscriptions/` | лента подписок |
| GET/POST | `/api/recipes/` | список / создание рецептов |
| GET/PATCH/DELETE | `/api/recipes/{id}/` | рецепт (изменять/удалять — только автор) |
| POST/DELETE | `/api/recipes/{id}/favorite/` | избранное |
| POST/DELETE | `/api/recipes/{id}/shopping_cart/` | список покупок |
| GET | `/api/recipes/download_shopping_cart/` | выгрузка списка покупок |
| GET | `/api/tags/`, `/api/ingredients/` | теги, ингредиенты (поиск `?name=`) |

## Переменные окружения

Приложение читает конфигурацию из `.env` (файл в `.gitignore`, не коммитится).
`DJANGO_SECRET_KEY` и `POSTGRES_PASSWORD` обязательны — без них проект не
стартует.

```env
# Django
DEBUG=False
DJANGO_SECRET_KEY=замените-на-свой-ключ
SECURE_SSL_REDIRECT=False

# PostgreSQL
POSTGRES_DB=foodgram
POSTGRES_USER=foodgram_user
POSTGRES_PASSWORD=замените-на-свой-пароль
DB_HOST=db          # 'db' для docker-compose; '127.0.0.1' для локального venv
DB_PORT=5432
```

Сгенерировать секретный ключ:

```bash
python -c "from django.core.management.utils import get_random_secret_key as k; print(k())"
```

## Локальное развёртывание

### Вариант 1. Полный стек в Docker (рекомендуется)

Поднимает весь сервис (БД + бэкенд + сборку фронтенда + nginx) и отдаёт его
на `http://localhost:7000`.

```bash
# 1. Клонировать репозиторий
git clone https://github.com/davoronov550/foodgram-project-react.git
cd foodgram-project-react

# 2. Создать .env в корне проекта (см. раздел выше), для compose DB_HOST=db

# 3. Собрать и запустить контейнеры
cd infra
docker compose up -d --build

# 4. Применить миграции и наполнить БД ингредиентами и тегами
docker compose exec backend python manage.py migrate
docker compose exec backend python manage.py import

# 5. (Опционально) создать суперпользователя для админки
docker compose exec backend python manage.py createsuperuser
```

Приложение: `http://localhost:7000`, API: `http://localhost:7000/api/`.

Остановить: `docker compose down` (добавьте `-v`, чтобы удалить и данные БД).

### Вариант 2. Локальная разработка (venv + PostgreSQL в контейнере)

Бэкенд запускается в виртуальном окружении, а PostgreSQL — в контейнере.

```bash
# 1. Виртуальное окружение и зависимости
cd backend
python -m venv venv
source venv/Scripts/activate        # Windows (Git Bash); Linux/macOS: source venv/bin/activate
pip install -r requirements.txt

# 2. PostgreSQL в контейнере (порт проброшен на localhost)
docker run -d --name foodgram-db \
  -e POSTGRES_DB=foodgram \
  -e POSTGRES_USER=foodgram_user \
  -e POSTGRES_PASSWORD=foodgram_local_pass \
  -p 5432:5432 -v foodgram_pgdata:/var/lib/postgresql/data \
  postgres:13.10

# 3. Создать backend/.env (DB_HOST=127.0.0.1, DEBUG=True)

# 4. Миграции, наполнение БД и запуск
python manage.py migrate
python manage.py import
python manage.py runserver
```

API будет доступно на `http://127.0.0.1:8000/api/`.

## Тестирование

Тесты (154 шт.) покрывают модели, сериализаторы, вьюсеты/эндпоинты, фильтры,
права и сервисы. Требуется доступная БД (см. Вариант 2).

```bash
cd backend
python manage.py test
# с отчётом о покрытии:
coverage run --source=api,recipes,users manage.py test
coverage report -m
```

## CI/CD

При пуше в репозиторий GitHub Actions прогоняет flake8 и тесты Django, собирает
и публикует Docker-образы бэкенда и фронтенда, после чего деплоит стек на
сервер (`.github/workflows/main.yml`).

## Автор

Daniil Voronov — [github.com/davoronov550](https://github.com/davoronov550)
