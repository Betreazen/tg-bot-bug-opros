# Telegram-бот для сбора обращений об ошибках

Бот собирает от пользователей структурированные обращения о проблемах с доступом/ошибках через пошаговый опрос из 4 вопросов. Ответы и скриншоты сохраняются на сервере в виде дерева папок. Администраторы могут выгрузить всю базу одним ZIP-архивом.

## Возможности

- Пошаговый опрос (VPN, регион, оператор, скриншот ошибки)
- Приём текста и изображений (JPEG/PNG), до 5 скриншотов на обращение
- Подтверждение при пустом ответе на последний вопрос
- Таймаут сессии по бездействию (10 мин, настраивается)
- Роль администратора: экспорт базы обращений в ZIP
- Все фразы бота вынесены в `phrases.json` — правка текстов без изменения кода
- Docker-контейнеризация с изолированной сетью

## Структура проекта

```
├── docker-compose.yml        # Развёртывание (один сервис)
├── Dockerfile                # Образ Python 3.12-slim
├── .env.example              # Шаблон переменных окружения
├── requirements.txt          # Зависимости (aiogram, aiosqlite)
├── phrases.json              # Все фразы бота (RU)
├── .gitignore
└── app/
    ├── main.py               # Точка входа
    ├── config.py             # Конфигурация из .env
    ├── phrases.py            # Загрузка фраз
    ├── states.py             # FSM-состояния опроса
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

Заполните:

```env
BOT_TOKEN=123456:ABC-DEF...         # Токен от @BotFather
ADMIN_IDS=123456789,987654321       # Telegram ID администраторов
TIMEOUT_SECONDS=600                 # Таймаут сессии (секунды)
DATA_DIR=/app/data                  # Не менять (путь внутри контейнера)
```

> **Как узнать свой Telegram ID:** отправьте любое сообщение боту [@userinfobot](https://t.me/userinfobot)

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

| Переменная | Назначение | Пример |
|------------|-----------|--------|
| `BOT_TOKEN` | Токен бота от BotFather | `123456:ABC-DEF...` |
| `ADMIN_IDS` | Telegram ID админов через запятую | `123456789,987654321` |
| `TIMEOUT_SECONDS` | Таймаут бездействия (сек) | `600` |
| `DATA_DIR` | Путь к данным внутри контейнера | `/app/data` |

## Изменение текстов бота

Все фразы находятся в файле `phrases.json`. После редактирования — перезапустите контейнер:

```bash
docker compose up -d --build
```

## Лицензия

MIT