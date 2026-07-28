# Tinder Diploma Infrastructure

Инфраструктурный слой для диплома.

## Быстрый запуск

1. Скопируйте файл окружения:
   `cp .env.example .env`

2. Запустите сервисы в Docker:
   `docker compose up -d`

## Доступные сервисы

* **PostgreSQL (PostGIS):** `localhost:5432`
* **Redis:** `localhost:6379`
* **MinIO API:** `localhost:9000`
* **MinIO Console (Web UI):** `http://localhost:9001`