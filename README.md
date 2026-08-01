# Crushme (Tinder Clone)

Веб-сервіс знайомств з режимом Friend Finder (BFF).

## Швидкий запуск

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
