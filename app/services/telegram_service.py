from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.exceptions import TelegramBadRequest
import asyncio
import json
from app.database import engine
from app.models import ProductModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.scheduler import scheduler
import os
import threading
import httpx

from dotenv import load_dotenv
load_dotenv()
# Получите токен из переменной окружения или укажите напрямую
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
ALLOWED_USER_IDS = [int(x) for x in os.getenv("ALLOWED_USER_IDS", "").split(",") if x]  # Список разрешенных пользователей

bot = None
dp = None

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")

async def init_telegram_bot():
    """Инициализирует Telegram бота"""
    global bot, dp
    bot = Bot(token=TELEGRAM_BOT_TOKEN)
    dp = Dispatcher()
    
    # Регистрация обработчиков
    dp.message.register(start_command, Command("start"))
    dp.message.register(help_command, Command("help"))
    dp.message.register(stats_command, Command("stats"))
    dp.callback_query.register(handle_callback)
    
    # Запуск polling в фоне
    asyncio.create_task(dp.start_polling(bot))
    print("✅ Telegram бот инициализирован")

async def send_telegram_notification(chat_id: int, message: str, parse_mode: str = None):
    """Отправляет уведомление в Telegram"""
    global bot
    if bot:
        try:
            await bot.send_message(chat_id=chat_id, text=message, parse_mode=parse_mode)
        except TelegramBadRequest as e:
            print(f"❌ Ошибка отправки в Telegram: {e}")

async def send_telegram_notification_with_keyboard(chat_id: int, message: str, keyboard: InlineKeyboardMarkup):
    """Отправляет уведомление с клавиатурой"""
    global bot
    if bot:
        try:
            await bot.send_message(chat_id=chat_id, text=message, reply_markup=keyboard)
        except TelegramBadRequest as e:
            print(f"❌ Ошибка отправки в Telegram: {e}")

# Обработчики команд
async def start_command(message: types.Message):
    """Обработчик команды /start"""
    if ALLOWED_USER_IDS and message.from_user.id not in ALLOWED_USER_IDS:
        await message.answer("❌ У вас нет доступа к этому боту")
        return
    
    keyboard = get_main_keyboard()
    await message.answer(
        "🤖 Добро пожаловать в бот управления парсером!\n\n"
        "Выберите действие:",
        reply_markup=keyboard
    )

async def help_command(message: types.Message):
    """Обработчик команды /help"""
    help_text = """
📖 *Справка по боту:*

/start - Главное меню
/stats - Статистика товаров
/help - Эта справка

*Кнопки:*
🔍 Статистика - Показать количество товаров в БД
▶️ Запустить парсер - Запустить парсинг вручную
📊 Статус - Проверить статус парсера
⚙️ Настройки - Настройки парсера
    """
    await message.answer(help_text, parse_mode="Markdown")

async def stats_command(message: types.Message):
    """Обработчик команды /stats"""
    if ALLOWED_USER_IDS and message.from_user.id not in ALLOWED_USER_IDS:
        await message.answer("❌ У вас нет доступа")
        return
    
    stats = await get_stats()
    await message.answer(stats)

# Клавиатуры
def get_main_keyboard():
    """Главная клавиатура"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🔍 Статистика", callback_data="stats"),
            InlineKeyboardButton(text="▶️ Запустить парсер", callback_data="start_parser")
        ],
        [
            InlineKeyboardButton(text="📊 Статус парсера", callback_data="parser_status"),
            InlineKeyboardButton(text="🏆 Топ 10 игр", callback_data="top_games")
        ],
        [
            InlineKeyboardButton(text="📈 Последние товары", callback_data="last_products")
        ]
    ])
    return keyboard


# Обработчик callback кнопок
async def handle_callback(callback: CallbackQuery):
    """Обработчик нажатий на кнопки"""
    if ALLOWED_USER_IDS and callback.from_user.id not in ALLOWED_USER_IDS:
        await callback.answer("❌ У вас нет доступа", show_alert=True)
        return
    
    data = callback.data
    chat_id = callback.from_user.id
    
    if data == "stats":
        stats = await get_stats()
        try:
            await callback.message.edit_text(stats, reply_markup=get_main_keyboard(), parse_mode="Markdown")
        except TelegramBadRequest as e:
            if "message is not modified" in str(e):
                await callback.answer("Статистика актуальна")
            else:
                raise
        await callback.answer()
    
    elif data == "start_parser":
        await callback.answer("🚀 Запускаю парсер...")
        await send_telegram_notification(chat_id, "🚀 Парсер запущен вручную!")
        
        from app.services.parser_service import OzonParser
        
        ozon_parser = OzonParser()
        category_url = "https://www.ozon.ru/category/nastolnye-igry-13507/"
        thread = threading.Thread(target=ozon_parser.start, args=(category_url,))
        thread.start()
    
    elif data == "parser_status":
        status = await get_parser_status()
        try:
            await callback.message.edit_text(status, reply_markup=get_main_keyboard(), parse_mode="Markdown")
        except TelegramBadRequest as e:
            if "message is not modified" in str(e):
                await callback.answer("Статус актуален")
            else:
                raise
        await callback.answer()
    
    elif data == "top_games":  # НОВАЯ КНОПКА
        top_games = await get_top_games_with_discount(10)
        try:
            await callback.message.edit_text(top_games, reply_markup=get_main_keyboard(), parse_mode="Markdown")
        except TelegramBadRequest as e:
            if "message is not modified" in str(e):
                await callback.answer("Список актуален")
            else:
                raise
        await callback.answer()
    
    elif data == "last_products":
        products = await get_last_products(5)
        try:
            await callback.message.edit_text(products, reply_markup=get_main_keyboard(), parse_mode="Markdown")
        except TelegramBadRequest as e:
            if "message is not modified" in str(e):
                await callback.answer("Список актуален")
            else:
                raise
        await callback.answer()
    
    elif data == "main_menu":
        try:
            await callback.message.edit_text(
                "🤖 *Главное меню:*\n\nВыберите действие:",
                reply_markup=get_main_keyboard(),
                parse_mode="Markdown"
            )
        except TelegramBadRequest as e:
            if "message is not modified" in str(e):
                await callback.answer()
            else:
                raise
        await callback.answer()

# Вспомогательные функции
async def get_stats():
    """Получить статистику через API"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{API_BASE_URL}/products/stats")
            response.raise_for_status()
            data = response.json()
            
            total = data.get("total", 0)
            if total == 0:
                return "📊 *Статистика:*\n\nТоваров в базе: 0"
            
            last_update = data.get("last_update")
            last_product = data.get("last_product")
            
            if last_update:
                from datetime import datetime
                last_date = datetime.fromisoformat(last_update).strftime("%d.%m.%Y %H:%M")
            else:
                last_date = "Нет данных"
            
            return (
                f"📊 *Статистика:*\n\n"
                f"📦 Всего товаров: *{total}*\n"
                f"🕐 Последнее обновление: {last_date}\n"
                f"🔗 Последний товар: {last_product['name'][:50] if last_product and last_product.get('name') else 'Нет'}"
            )
    except Exception as e:
        print(f"Ошибка при получении статистики: {e}")
        return "❌ Ошибка при получении статистики"

async def get_parser_status():
    """Получить статус парсера"""
    jobs = scheduler.get_jobs()
    if jobs:
        next_run = jobs[0].next_run_time
        next_run_str = next_run.strftime("%d.%m.%Y %H:%M") if next_run else "Не запланировано"
        return (
            f"📊 *Статус парсера:*\n\n"
            f"✅ Планировщик активен\n"
            f"⏰ Следующий запуск: {next_run_str}\n"
            f"🔄 Интервал: каждый час"
        )
    return "❌ Планировщик не активен"

async def get_last_products(limit: int = 5):
    """Получить последние товары через API"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{API_BASE_URL}/products/last", params={"limit": limit})
            response.raise_for_status()
            products = response.json()
            
            if not products:
                return "📦 Последние товары не найдены"
            
            text = f"📦 *Последние {len(products)} товаров:*\n\n"
            for i, product in enumerate(products, 1):
                text += f"{i}. {product['name'][:40]}...\n"
                text += f"   💰 {product['price']}\n"
                text += f"   🔗 {product['link'][:50]}...\n\n"
            
            return text
    except Exception as e:
        print(f"Ошибка при получении последних товаров: {e}")
        return "❌ Ошибка при получении товаров"

async def get_top_games_with_discount(limit: int = 10):
    """Получить топ игр со скидкой через API"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{API_BASE_URL}/products/top-discount", params={"limit": limit})
            response.raise_for_status()
            products = response.json()
            
            if not products:
                return "🏆 *Топ игр со скидкой:*\n\nТовары не найдены"
            
            text = f"🏆 *Топ {len(products)} игр с наибольшей скидкой:*\n\n"
            for i, product in enumerate(products, 1):
                if product.get('discount', 0) > 0:
                    text += f"{i}. *{product['name'][:40]}...*\n"
                    text += f"   💰 {product['price']}\n"
                    text += f"   🔥 Скидка: *-{product['discount']:.0f}%*\n"
                    text += f"   🔗 {product['link'][:50]}...\n\n"
                else:
                    text += f"{i}. *{product['name'][:40]}...*\n"
                    text += f"   💰 {product['price']}\n"
                    text += f"   🔗 {product['link'][:50]}...\n\n"
            
            return text
    except Exception as e:
        print(f"Ошибка при получении топ игр: {e}")
        return "❌ Ошибка при получении топ игр"

# Функция для отправки уведомлений из парсера
def send_parser_notification(chat_ids: list[int], message: str):
    """Отправляет уведомление о парсере через Telegram HTTP API (синхронно)"""
    if not TELEGRAM_BOT_TOKEN or TELEGRAM_BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        print("⚠️ Telegram бот не настроен")
        return
    
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    
    for chat_id in chat_ids:
        try:
            # Используем синхронный HTTP запрос
            with httpx.Client(timeout=10.0) as client:
                response = client.post(
                    url,
                    json={
                        "chat_id": chat_id,
                        "text": message,
                        "parse_mode": "Markdown"
                    }
                )
                response.raise_for_status()
                print(f"✅ Уведомление отправлено в Telegram (chat_id: {chat_id})")
        except Exception as e:
            print(f"❌ Ошибка отправки в Telegram: {e}")