# 🐸 Froggy Coder

**Froggy Coder** начинался как обучающая игра на `Python + Pygame`, а теперь в репозитории есть и полноценная fullstack-версия для портфолио.

## Что теперь есть

- веб-клиент на `React + Vite + TypeScript`;
- backend API на `FastAPI`;
- база данных `SQLite`;
- регистрация и вход;
- автоматический 4-значный тэг у профиля, чтобы одинаковые имена не конфликтовали;
- прогресс пользователя на сервере;
- таблица лидеров;
- админка для добавления, редактирования и удаления вопросов;
- болотный стиль и связь с оригинальной `pygame`-игрой.

## Архитектура

### Frontend

- отвечает за интерфейс, маршруты внутри приложения и отправку действий пользователя;
- загружает вопросы, прогресс и лидерборд через API;
- не хранит вопросы как источник правды.

### Backend

- хранит пользователей, сессии, вопросы, попытки, результаты и прогресс;
- проверяет ответы на сервере;
- считает результаты и лидерборд;
- отдает admin CRUD для вопросов.

### База данных

SQLite хранит:

- пользователей;
- токены сессий;
- вопросы и правильные ответы;
- попытки ответов;
- прогресс;
- результаты забегов.

## Структура проекта

```text
.
├── docker/
│   └── nginx.conf
├── backend/
│   ├── auth.py
│   ├── db.py
│   ├── main.py
│   ├── schemas.py
│   └── seed_data.py
├── Dockerfile.backend
├── Dockerfile.frontend
├── docker-compose.yml
├── public/
├── src/
│   ├── api.ts
│   ├── App.tsx
│   ├── main.tsx
│   ├── styles.css
│   ├── types.ts
│   └── vite-env.d.ts
├── game.py
├── requirements.txt
├── package.json
├── vite.config.ts
└── render.yaml
```

## Локальный запуск

### Быстрый запуск через Docker

Если хочется поднимать frontend и backend одной командой:

```bash
docker compose up --build
```

После старта будут доступны:

```text
Frontend: http://127.0.0.1:8080
Backend API: http://127.0.0.1:8000
Swagger: http://127.0.0.1:8000/docs
```

Что делает `docker compose`:

- собирает frontend в production-режиме;
- поднимает `FastAPI` backend;
- проксирует запросы `/api` с frontend на backend;
- сохраняет `SQLite` в named volume `froggy_data`, чтобы база не терялась после перезапуска контейнеров.

Если нужно переопределить админ-логин и пароль, можно запустить так:

```bash
FROGGY_ADMIN_USERNAME=my_admin FROGGY_ADMIN_PASSWORD=my_secret_password docker compose up --build
```

Остановка:

```bash
docker compose down
```

### 1. Backend

Требования:

- Python 3.9+
- `pip`

Установка и запуск:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn backend.main:app --reload --port 8000
```

API будет доступен на:

```text
http://127.0.0.1:8000
```

Swagger:

```text
http://127.0.0.1:8000/docs
```

### 2. Frontend

Требования:

- Node.js
- npm

Установка и запуск:

```bash
npm install
npm run dev
```

Фронтенд будет доступен на:

```text
http://127.0.0.1:5173
```

`vite.config.ts` уже настроен так, чтобы в dev-режиме проксировать `/api` на `http://127.0.0.1:8000`.

## Дефолтный админ

При первом запуске backend создает admin-пользователя, если админов еще нет.

По умолчанию:

- логин: `frog_admin`
- пароль: `admin12345`

Для нормального запуска лучше переопределить через переменные окружения:

```bash
export FROGGY_ADMIN_USERNAME=my_admin
export FROGGY_ADMIN_PASSWORD=my_secret_password
```

## Основные API-эндпоинты

### Auth

- `POST /api/auth/register`
- `POST /api/auth/login`
- `GET /api/auth/me`
- `POST /api/auth/logout`

При регистрации игрок получает тэг из 4 разных цифр, поэтому в интерфейсе логин выглядит как `имя#1234`.
Для входа новых аккаунтов используйте именно этот формат.

### Game

- `GET /api/game/bootstrap`
- `POST /api/game/reset`
- `POST /api/game/submit-answer`

### Leaderboard

- `GET /api/leaderboard`

### Admin

- `GET /api/admin/questions`
- `POST /api/admin/questions`
- `PUT /api/admin/questions/{id}`
- `DELETE /api/admin/questions/{id}`

## Deploy

В репозитории есть `render.yaml` для деплоя на Render:

- backend как Python web service;
- frontend как static site;
- SQLite через persistent disk для backend.

Важно:

- у Render файловая система по умолчанию эфемерная, поэтому для SQLite нужен persistent disk;
- persistent disk на Render доступен не на free web service, а на платном плане;
- для фронтенда нужно указать `VITE_API_BASE_URL` как публичный URL backend.

Базовый сценарий деплоя:

1. Запушить проект в GitHub.
2. Подключить репозиторий к Render.
3. Создать Blueprint из `render.yaml`.
4. Для backend задать секрет `FROGGY_ADMIN_PASSWORD`.
5. Для frontend задать `VITE_API_BASE_URL`, например `https://your-api.onrender.com/api`.
6. После деплоя открыть frontend по публичной ссылке Render.

## Desktop-версия

Старая `pygame`-версия никуда не делась и по-прежнему лежит в [game.py](game.py).  
Это полезно для портфолио: можно показать эволюцию проекта от локальной игры до fullstack-приложения.

Запуск desktop-версии:

```bash
python3 game.py
```
