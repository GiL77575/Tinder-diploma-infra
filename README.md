# Crushme (Tinder Clone)

Веб-сервіс знайомств з режимом Friend Finder (BFF).

## Хостинг

Прод працює на **VPS** через Docker Compose (`crush.pp.ua`).  
Render / інші PaaS **не використовуються**.

Деплой на сервері:

```bash
git pull
docker compose up -d --build
docker compose exec web python manage.py migrate
```

CI (GitHub Actions) лише валідує `docker compose` і збірку образів — автоматичний деплой на VPS з Actions поки не налаштований.

## Швидкий запуск (локально)

1. Скопіюйте файл оточення:
   `cp .env.example .env`

2. Запустіть сервіси в Docker:
   `docker compose up -d --build`

3. Застосуйте міграції:
   `docker compose exec web python manage.py migrate`

## Доступні сервіси

* **Django:** `http://localhost:8000`
* **PostgreSQL:** `localhost:5432`
* **Redis:** `localhost:6379`

## Структура

* `backend/` — Django apps, моделі, settings
* `frontend/` — templates і static (HTML, CSS, JS, HTMX)
