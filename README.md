# Froggy Coder

`Froggy Coder` вырос из локальной `pygame`-игры в fullstack-проект с веб-клиентом, backend API и серверным хранением прогресса.

## Что есть сейчас

- frontend на `React + Vite + TypeScript`;
- backend на `FastAPI`;
- `SQLite` для пользователей, вопросов, прогресса и результатов;
- регистрация и вход;
- таблица лидеров;
- магазин и внутриигровая валюта;
- admin CRUD для вопросов;
- admin CRUD для промокодов;
- ежедневный вопрос с отдельным рейтингом дня;
- экспорт прогресса в PDF;
- опциональный таймер на вопрос на frontend;
- cookie-based авторизация с CSRF-защитой.

## Безопасность и конфиг

Секреты и runtime-настройки больше не захардкожены в коде.

1. Скопируйте `.env.example` в `.env`.
2. Укажите сильный `FROGGY_ADMIN_PASSWORD`.
3. При необходимости настройте `FROGGY_ALLOWED_ORIGINS`, `FROGGY_COOKIE_SECURE` и параметры перевода.

Пример:

```env
FROGGY_ADMIN_USERNAME=frog_admin
FROGGY_ADMIN_PASSWORD=replace-with-a-strong-secret
FROGGY_ALLOWED_ORIGINS=http://localhost:5173,http://127.0.0.1:5173,http://localhost:8080,http://127.0.0.1:8080
FROGGY_COOKIE_SECURE=false
FROGGY_COOKIE_SAMESITE=lax
FROGGY_TRANSLATION_API_BASE_URL=http://translator:5000
FROGGY_TRANSLATION_TIMEOUT_SECONDS=5
VITE_API_BASE_URL=/api
```

Важно:

- backend больше не использует дефолтный пароль `admin12345`;
- при старте пароль админа синхронизируется из `.env`, даже если пользователь `frog_admin` уже есть в базе;
- авторизация работает через `HttpOnly` cookie, а не через `Bearer` в `localStorage`;
- CSRF-токен возвращается в ответе auth/session и хранится в состоянии frontend, а не дублируется в cookie;
- все `POST`/`PUT`/`DELETE` защищены CSRF-токеном;
- CORS задаётся через `FROGGY_ALLOWED_ORIGINS`.
- перевод вопросов, магазина и части интерфейсных текстов идет через LibreTranslate-compatible API; в Docker по умолчанию поднимается локальный `translator`-контейнер;
- публичные fallback-серверы перевода отключены: если `FROGGY_TRANSLATION_API_BASE_URL` не задан, backend тихо вернёт исходный текст;
- при необходимости можно указать свой `FROGGY_TRANSLATION_API_BASE_URL` и `FROGGY_TRANSLATION_API_KEY`.

Если перевод не работает, почти всегда причина одна из двух:

- backend не получил `FROGGY_TRANSLATION_API_BASE_URL`;
- указан endpoint, до которого контейнер не может достучаться.

Для Docker проще всего:

1. Скопируй `.env.example` в `.env`.
2. Оставь `FROGGY_TRANSLATION_API_BASE_URL=http://translator:5000`, чтобы backend ходил в локальный контейнер.
3. Если используешь свой сервис, проверь, что URL доступен именно из контейнера `backend`.
4. Если перевод недоступен, backend вернёт оригинальный текст, не обращаясь к публичным proxy-серверам.

Первый запуск может быть долгим, потому что `translator` скачивает модели.
Если хочешь свой отдельный LibreTranslate вне этого compose, пропиши в `.env` его реальный адрес.

## Структура проекта

```text
.
├── backend/
│   ├── auth.py
│   ├── config.py
│   ├── db.py
│   ├── main.py
│   ├── schemas.py
│   └── seed_data.py
├── docker/
│   └── nginx.conf
├── src/
│   ├── App.tsx
│   ├── api.ts
│   ├── main.tsx
│   ├── styles.css
│   └── types.ts
├── tests/
│   └── test_api.py
├── .env.example
├── docker-compose.yml
├── Dockerfile.backend
├── Dockerfile.frontend
├── render.yaml
└── requirements.txt
```

## Локальный запуск

### Docker

`docker compose` читает переменные из `.env` автоматически.

```bash
docker compose up --build
```

После старта:

- frontend: `http://127.0.0.1:8080`
- backend API: `http://127.0.0.1:8000`
- Swagger: `http://127.0.0.1:8000/docs`

Остановка:

```bash
docker compose down
```

### Backend

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn backend.main:app --reload --port 8000
```

### Frontend

```bash
npm install
npm run dev
```

В dev-режиме `Vite` проксирует `/api` на `http://127.0.0.1:8000`.

## Авторизация

Схема теперь такая:

- `POST /api/auth/register` создаёт аккаунт, выставляет session cookie и возвращает пользователя + `csrf_token`;
- `POST /api/auth/login` делает то же самое для существующего пользователя;
- `GET /api/auth/session` восстанавливает состояние текущей сессии;
- `GET /api/auth/me` возвращает текущего пользователя;
- `GET /api/auth/progress-report?locale=ru|en|zh` формирует локализованный PDF-отчёт по текущему прогрессу;
- `POST /api/auth/redeem-promo` активирует промокод для аккаунта;
- `POST /api/auth/logout` удаляет серверную сессию и очищает cookie.

Frontend отправляет запросы с `credentials: "include"` и больше не хранит токен в `localStorage`.

## Основные API-эндпоинты

### Auth

- `POST /api/auth/register`
- `POST /api/auth/login`
- `GET /api/auth/session`
- `GET /api/auth/me`
- `GET /api/auth/progress-report?locale=ru|en|zh`
- `PUT /api/auth/profile`
- `POST /api/auth/redeem-promo`
- `POST /api/auth/logout`

### Game

- `GET /api/game/routes`
- `GET /api/game/bootstrap`
- `GET /api/game/progress`
- `GET /api/game/daily-challenge`
- `POST /api/game/daily-challenge`
- `POST /api/game/reset`
- `POST /api/game/reset-all`
- `POST /api/game/select-level`
- `POST /api/game/reset-level`
- `POST /api/game/submit-answer`

### Shop

- `GET /api/shop`
- `POST /api/shop/items/{item_id}`

### Leaderboard

- `GET /api/leaderboard`

### Admin

- `GET /api/admin/questions`
- `POST /api/admin/questions`
- `PUT /api/admin/questions/{id}`
- `DELETE /api/admin/questions/{id}`
- `GET /api/admin/promos`
- `POST /api/admin/promos`
- `PUT /api/admin/promos/{code}`
- `DELETE /api/admin/promos/{code}`

Для admin CRUD backend теперь валидирует `topic` и возвращает `400`, если маршрута не существует.

## Что добавлено поверх базовой игры

- лидерборд по `coins` теперь route-scoped: для каждого `topic` считается свой рейтинг, а не общий кошелек по всем маршрутам;
- генерация пользовательского тега защищена от коллизий через транзакцию и retry при `IntegrityError`;
- админка умеет создавать, редактировать, отключать и удалять промокоды;
- в профиле появился экспорт прогресса в PDF, а в приложении отдельный экран для ежедневного вопроса;
- таймер на вопрос сделан как опциональный frontend-режим: по истечении времени попытка уходит как неверная.

## Тесты и smoke-checks

Backend smoke/API tests:

```bash
.venv/bin/pytest tests/test_api.py -q
```

Frontend smoke-check:

```bash
npm run build
```

Сейчас тесты покрывают:

- регистрацию и восстановление cookie-сессии;
- CSRF-защиту mutating-endpoints;
- admin CRUD и запрет несуществующих `topic`;
- retry при коллизии пользовательского тега;
- route-scoped leaderboards по `coins`;
- admin promo CRUD и активацию промокодов;
- daily challenge и выдачу PDF-отчёта.

## Deploy

В `render.yaml` уже подготовлены:

- backend service;
- static frontend;
- persistent disk для `SQLite`.

Для продакшена обязательно задайте:

- `FROGGY_ADMIN_PASSWORD`
- `FROGGY_ALLOWED_ORIGINS`
- `FROGGY_COOKIE_SECURE=true`
- `VITE_API_BASE_URL`

## Desktop-версия

Старая `pygame`-версия осталась в [game.py](./game.py).

Запуск:

```bash
python3 game.py
```
