# Telegram-бот для сбора обращений об ошибках

Бот собирает от пользователей структурированные обращения о проблемах с доступом/ошибках через пошаговый опрос из 4 вопросов. Ответы и скриншоты сохраняются на сервере в виде дерева папок. Администраторы могут выгрузить всю базу одним ZIP-архивом.

## Возможности

- Пошаговый опрос (VPN, регион, оператор, скриншот ошибки)
- Приём текста и изображений (JPEG/PNG), до 5 скриншотов на обращение
- Подтверждение при пустом ответе на последний вопрос
- Таймаут сессии по бездействию (10 мин, настраивается)
- Роль администратора: экспорт базы обращений в ZIP
- Все фразы бота вынесены в `phrases.json` — правка текстов без изменения кода
- Сессии хранятся в Redis и переживают перезапуск контейнера
- Атомарное сохранение обращений (папка либо целиком записана, либо отсутствует)
- Корректная обработка альбомов (несколько скриншотов одним сообщением)
- Docker-контейнеризация; все имена ресурсов изолированы через `COMPOSE_PROJECT_NAME` — бот не конфликтует с другими ботами на сервере и не публикует порты

## Структура проекта

```
├── docker-compose.yml        # Развёртывание (бот + Redis)
├── Dockerfile                # Образ Python 3.12-slim
├── .dockerignore             # Что не копировать в образ
├── .env.example              # Шаблон переменных окружения
├── requirements.txt          # Зависимости (aiogram, aiosqlite, redis)
├── phrases.json              # Все фразы бота (RU)
├── .gitignore
└── app/
    ├── main.py               # Точка входа
    ├── config.py             # Конфигурация из .env
    ├── phrases.py            # Загрузка фраз
    ├── states.py             # FSM-состояния опроса
    ├── timeouts.py           # Таймауты сессий (Redis-sweeper)
    ├── keyboards.py          # Клавиатуры
    ├── db.py                 # SQLite (метаданные)
    ├── storage.py            # Файловая система (обращения)
    ├── export.py             # Сборка ZIP-архива
    └── handlers/
        ├── common.py         # /start, маршрутизация
        ├── survey.py         # Логика опроса
        └── admin.py          # Админ-функции
```

## Хранение данных

```
data/
├── bot.db                    # SQLite (индекс, не входит в экспорт)
├── 1/                        # Папка пользователя (internal_id)
│   ├── request_1/
│   │   ├── answers.txt
│   │   └── screenshot_1.jpg
│   └── request_2/
│       └── answers.txt
└── 2/
    └── request_1/
        └── answers.txt
```

---

## Руководство по развёртыванию на Ubuntu

### Требования

- Ubuntu 20.04+ (рекомендуется 22.04 LTS)
- Docker Engine 24+
- Docker Compose v2+
- Git

### 1. Установка Docker (если не установлен)

```bash
# Обновление пакетов
sudo apt update && sudo apt upgrade -y

# Установка зависимостей
sudo apt install -y ca-certificates curl gnupg

# Добавление GPG-ключа Docker
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

# Добавление репозитория
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo $VERSION_CODENAME) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Установка Docker
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

# Добавление текущего пользователя в группу docker (чтобы не использовать sudo)
sudo usermod -aG docker $USER
newgrp docker
```

### 2. Клонирование репозитория

```bash
cd /opt
sudo git clone https://github.com/YOUR_USERNAME/tg-bot-bug-opros.git
sudo chown -R $USER:$USER tg-bot-bug-opros
cd tg-bot-bug-opros
```

### 3. Настройка конфигурации

```bash
cp .env.example .env
nano .env
```

Обязательно заполнить только две строки — `BOT_TOKEN` и `ADMIN_IDS`:

```env
BOT_TOKEN=123456:ABC-DEF...         # Токен от @BotFather
ADMIN_IDS=123456789,987654321       # Telegram ID администраторов
```

Остальные переменные имеют значения по умолчанию и в большинстве случаев не требуют изменений. `REDIS_URL` и `DATA_DIR` задаются автоматически в `docker-compose.yml` — трогать не нужно.

> **Как узнать свой Telegram ID:** отправьте любое сообщение боту [@userinfobot](https://t.me/userinfobot)

> **Несколько ботов на одном сервере:** имена контейнеров, сети и тома берутся из `COMPOSE_PROJECT_NAME` в `.env` (по умолчанию `tg-bug-opros`). Если на сервере уже есть стек с таким именем — задайте другое уникальное значение, и конфликтов не будет. Бот работает по long-polling и не открывает портов, поэтому конфликта портов с другими ботами нет в принципе.

### 4. Запуск

```bash
docker compose up -d
```

Проверка статуса:

```bash
docker compose logs -f
```

Остановка:

```bash
docker compose down
```

### 5. Обновление бота

```bash
cd /opt/tg-bot-bug-opros
git pull
docker compose up -d --build
```

### 6. Бэкап данных

Все данные хранятся в папке `./data`. Для полного бэкапа:

```bash
tar -czf backup_$(date +%Y%m%d).tar.gz data/
```

Восстановление:

```bash
tar -xzf backup_YYYYMMDD.tar.gz
```

### 7. Просмотр логов

```bash
# Последние 100 строк
docker compose logs --tail=100

# В реальном времени
docker compose logs -f
```

### 8. Перезапуск

```bash
docker compose restart
```

---

## Конфигурация

| Переменная | Назначение | По умолчанию |
|------------|-----------|--------|
| `BOT_TOKEN` | Токен бота от BotFather (**обязательно**) | — |
| `ADMIN_IDS` | Telegram ID админов через запятую (**обязательно**) | — |
| `COMPOSE_PROJECT_NAME` | Префикс имён контейнеров/сети/тома (изоляция) | `tg-bug-opros` |
| `TIMEOUT_SECONDS` | Таймаут бездействия (сек) | `600` |
| `MAX_SCREENSHOT_BYTES` | Лимит размера одного скриншота (байт) | `10485760` |
| `REDIS_URL` | Адрес Redis (задаётся в compose) | `redis://redis:6379/0` |
| `DATA_DIR` | Путь к данным внутри контейнера (задаётся в compose) | `/app/data` |

## Изменение текстов бота

Все фразы находятся в файле `phrases.json`. После редактирования — перезапустите контейнер:

```bash
docker compose up -d --build
```

## Тесты

```bash
pip install -r requirements-dev.txt
pytest
```

Полный набор (хендлеры, storage, таймауты — с моками `aiogram`/redis) требует
установленного `aiogram`. Если локальная версия Python слишком новая для колёс
`aiogram`, тесты этих модулей автоматически пропускаются. Прогнать всё можно в
контейнере на Python 3.12:

```bash
docker run --rm -v "$PWD":/app -w /app python:3.12-slim \
  sh -c "pip install -q -r requirements-dev.txt && pytest -q"
```

## Лицензия

MIT