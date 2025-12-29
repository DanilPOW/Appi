from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.database import engine
from app.models import ProductModel
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession
import asyncio

scheduler = AsyncIOScheduler()

async def clear_products_table():
    """Очищает таблицу товаров перед новым парсингом"""
    async with AsyncSession(engine) as session:
        try:
            await session.execute(delete(ProductModel))
            await session.commit()
            print("Таблица товаров очищена")
        except Exception as e:
            await session.rollback()
            print(f"Ошибка при очистке таблицы: {e}")

def run_parser():
    """Запускает парсер с очисткой таблицы"""
    from app.services.parser_service import OzonParser
    
    # Очищаем таблицу перед парсингом
    new_loop = asyncio.new_event_loop()
    asyncio.set_event_loop(new_loop)
    try:
        new_loop.run_until_complete(clear_products_table())
    finally:
        new_loop.close()
    
    # Запускаем парсер
    ozon_parser = OzonParser()
    category_url = "https://www.ozon.ru/category/nastolnye-igry-13507/"
    ozon_parser.start(category_url)

async def start_scheduler():
    scheduler.start()
    scheduler.add_job(run_parser, 'interval', minutes=10)

async def shutdown_scheduler():
    scheduler.shutdown()