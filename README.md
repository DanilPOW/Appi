ParsAPI - Парсер товаров Ozon

FastAPI приложение для парсинга товаров с Ozon с поддержкой Telegram бота и WebSocket.

## Быстрый старт

### 1. Установка зависимостей

python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/Mac

pip install -r requirements.txt
pip install apscheduler  # Добавить если отсутствует
playwright install

### 2. Настройка переменных окружения

Создайте файл `.env` в корне проекта:
TELEGRAM_BOT_TOKEN=your_bot_token_here
ALLOWED_USER_IDS=123456789
API_BASE_URL=http://localhost:8000

### 3. Запуск NATS Server

nats-server.exe


### 4. Запуск приложения

python main.pyПриложение доступно по адресу: `http://localhost:8000`
Документация API: `http://localhost:8000/docs`

## Основные endpoints

- `GET /products` - Список товаров
- `GET /products/stats` - Статистика
- `GET /parser` - Запуск парсера
- `WebSocket /ws` - Обновления в реальном времени

## Telegram бот

Команды: `/start`, `/help`, `/stats`, `/last`, `/top`, `/parse`

## Примечания

- Парсер автоматически запускается каждые 10 минут
- База данных SQLite создается автоматически (`tasks.db`)
- NATS должен быть запущен на `nats://127.0.0.1:4222`
