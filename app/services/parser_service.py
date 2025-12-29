from playwright.sync_api import sync_playwright
import time
import asyncio
import threading
import json
import re
from app.schemas import Product
from app.models import ProductModel
from app.database import engine
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.websocket_service import send_ws_notification
from app.services.telegram_service import send_parser_notification
import os
from dotenv import load_dotenv
load_dotenv()
import nats
import asyncio


_nc = None

def set_nats_connection(nc):
    """Установить NATS соединение для использования в парсере"""
    global _nc
    _nc = nc

async def publish_to_nats(channel: str, data: dict):
    """Публикация сообщения в NATS"""
    global _nc
    if _nc:
        try:
            message = json.dumps(data, ensure_ascii=False)
            await _nc.publish(channel, message.encode())
            print(f" Опубликовано в NATS канал '{channel}': {message[:100]}")
        except Exception as e:
            print(f" Ошибка публикации в NATS: {e}")

def publish_to_nats_sync(channel: str, data: dict):
    """Синхронная обертка для публикации в NATS"""
    if _nc:
        try:
            # Создаем новый event loop для публикации
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(publish_to_nats(channel, data))
            finally:
                loop.close()
        except Exception as e:
            print(f"❌ Ошибка синхронной публикации в NATS: {e}")


class OzonParser:
    def start(self, category_url: str):
        # Уведомление о запуске парсера
        chat_ids_str = os.getenv("ALLOWED_USER_IDS", "")
        TELEGRAM_CHAT_IDS = [int(x.strip()) for x in chat_ids_str.split(",") if x.strip()]
        
#        if TELEGRAM_CHAT_IDS:
#            send_parser_notification(
#                TELEGRAM_CHAT_IDS,
#                "*Парсер запущен*\n\nНачинаю сбор данных с Ozon..."
#            )

        send_ws_notification(json.dumps({
            "type": "parser_status",
            "status": "started",
            "message": "Парсер запущен, начинаю сбор данных..."
        }, ensure_ascii=False))
        
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=False,
                args=['--disable-blink-features=AutomationControlled']
            )
            context = browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                locale='ru-RU',
                extra_http_headers={'Accept-Language': 'ru-RU,ru;q=0.9'}
            )
            self.page = context.new_page()
            self.page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
            print(f"Открываю страницу: {category_url}")
            self.page.goto(category_url)
            time.sleep(2)  # Увеличено время ожидания
            
            # Уведомление о начале парсинга
            send_ws_notification(json.dumps({
                "type": "parser_status",
                "status": "parsing",
                "message": "Начинаю парсинг товаров..."
            }, ensure_ascii=False))
            
            # Парсим товары
            products = self.parce_products()
            print(f"Найдено товаров: {len(products)}")
            
            # Уведомление о завершении парсинга
            send_ws_notification(json.dumps({
                "type": "parser_status",
                "status": "parsed",
                "message": f"Парсинг завершен! Найдено товаров: {len(products)}"
            }, ensure_ascii=False))
            
            # Сохраняем в БД
            if products:
                send_ws_notification(json.dumps({
                    "type": "parser_status",
                    "status": "saving",
                    "message": "Сохраняю товары в базу данных..."
                }, ensure_ascii=False))
                self.save_products_to_db(products)
                
                # Уведомление об успешном сохранении
                send_ws_notification(json.dumps({
                    "type": "parser_status",
                    "status": "completed",
                    "message": f"Готово! Сохранено товаров: {len(products)}"
                }, ensure_ascii=False))

#                if TELEGRAM_CHAT_IDS:
#                    send_parser_notification(
#                        TELEGRAM_CHAT_IDS,
#                        f"✅ *Парсинг завершен*\n\n"
#                        f"📦 Найдено товаров: {len(products)}\n"
#                        f"💾 Сохранено в базу данных"
#                    )
            else:
                if TELEGRAM_CHAT_IDS:
                    send_parser_notification(
                        TELEGRAM_CHAT_IDS,
                        "⚠️ *Парсинг завершен*\n\nТовары не найдены"
                    )

                send_ws_notification(json.dumps({
                    "type": "parser_status",
                    "status": "error",
                    "message": "Товары не найдены"
                }, ensure_ascii=False))
    
    def parce_products(self, max_products: int = 100) -> list[Product]:
        products = []
        seen_links = set()
        
        try:
            self.page.wait_for_selector('#contentScrollPaginator', timeout=10000)
        except:
            return products
        
        scroll_num = 0
        no_new_count = 0
        
        while len(products) < max_products:
            scroll_num += 1
            
            # Проверяем, сколько карточек найдено
            cards = self.page.query_selector_all('#contentScrollPaginator [class*="tile-root"]')
            print(f"Найдено карточек на странице: {len(cards)}")
            
            if len(cards) == 0:
                # Пробуем альтернативные селекторы
                cards = self.page.query_selector_all('a[href*="/product/"]')
                print(f"Альтернативный поиск по ссылкам: {len(cards)}")
            
            new_count = 0
            for card in cards:
                try:
                    # Пробуем разные варианты поиска ссылки
                    link_elem = card.query_selector('a[data-prerender="true"]')
                    if not link_elem:
                        # Если карточка уже является ссылкой (проверяем через href)
                        try:
                            href = card.get_attribute('href')
                            if href and '/product/' in href:
                                link_elem = card
                            else:
                                link_elem = card.query_selector('a[href*="/product/"]')
                        except:
                            link_elem = card.query_selector('a[href*="/product/"]')
                    
                    if not link_elem:
                        continue
                    
                    link = link_elem.get_attribute('href')
                    if not link:
                        continue
                    
                    # Обрабатываем относительные ссылки
                    if link.startswith('/product/'):
                        link = 'https://www.ozon.ru' + link
                    
                    if link in seen_links or not '/product/' in link:
                        continue
                    
                    seen_links.add(link)
                    
                    # Название - пробуем разные селекторы
                    name = ""
                    name_selectors = [
                        'div.bq03_0_5-a span.tsBody500Medium',  # Точный селектор
                        'span.tsBody500Medium',
                        'div[class*="bq03_0_5-a"] span.tsBody500Medium',
                        'span.tsBody',
                        '[class*="tsBody"]',
                        '[class*="title"]',
                        'a span',
                        'div span'
                    ]
                    for selector in name_selectors:
                        name_elem = card.query_selector(selector)
                        if name_elem:
                            name_text = name_elem.inner_text().strip()
                            if name_text and name_text != "Распродажа":
                                name = name_text
                                break
                    
                    # Цена - пробуем разные селекторы
                    price = ""
                    price_selectors = [
                        'div.c35_3_11-a0 span.tsHeadline500Medium',  # Точный селектор
                        'span.tsHeadline500Medium',
                        'span[class*="price"]',
                        '[class*="tsHeadline"]',
                        '[class*="currency"]'
                    ]
                    for selector in price_selectors:
                        price_elem = card.query_selector(selector)
                        if price_elem:
                            price_text = price_elem.inner_text().strip()
                            if price_text:
                                price = price_text
                                break
                    
                    # Скидка - div.c35_3_11-a0 span.c35_3_11-b4
                    discount = 0.0
                    try:
                        discount_container = card.query_selector('div.c35_3_11-a0')
                        if discount_container:
                            discount_elem = discount_container.query_selector('span.c35_3_11-b4')
                            if discount_elem:
                                discount_text = discount_elem.inner_text().strip()
                                discount_match = re.search(r'(\d+)', discount_text.replace('−', '-').replace('–', '-'))
                                if discount_match:
                                    discount = float(discount_match.group(1))
                        else:
                            # Альтернативный поиск скидки
                            discount_elem = card.query_selector('span.c35_3_11-b4')
                            if discount_elem:
                                discount_text = discount_elem.inner_text().strip()
                                discount_match = re.search(r'(\d+)', discount_text.replace('−', '-').replace('–', '-'))
                                if discount_match:
                                    discount = float(discount_match.group(1))
                    except:
                        pass
                    
                    if link:  # Добавляем даже без названия для отладки
                        products.append(Product(
                            name=name or "Без названия", 
                            price=price or "Нет цены", 
                            link=link,
                            discount=discount
                        ))
                        new_count += 1
                        if len(products) >= max_products:
                            break
                except Exception as e:
                    print(f"Ошибка при парсинге карточки: {e}")
                    continue
            
            print(f"Скролл {scroll_num}: найдено новых товаров: {new_count}, всего: {len(products)}")
            
            if new_count == 0:
                no_new_count += 1
                if no_new_count >= 3:
                    print("Прекращено: нет новых товаров")
                    break
            else:
                no_new_count = 0
            
            if len(products) >= max_products:
                break
            
            self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(2)
        
        return products

    async def _save_products_async(self, products: list[Product]):
        """Асинхронное сохранение продуктов в БД"""
        async with AsyncSession(engine) as session:
            try:
                saved_products = []
                for product in products:
                    db_product = ProductModel(
                        name=product.name,
                        price=product.price,
                        link=product.link,
                        discount=product.discount
                    )
                    session.add(db_product)
                    saved_products.append({
                        "id": None,  # Будет установлен после commit
                        "name": product.name,
                        "price": product.price,
                        "link": product.link,
                        "discount": product.discount
                    })
                
                await session.commit()
                
                # Обновляем ID после сохранения
                for i, db_product in enumerate(saved_products):
                    # Получаем ID из сессии (после flush)
                    pass
                
                print(f"Сохранено {len(products)} товаров в БД")
                
                # Публикуем в NATS о сохранении товаров
                await publish_to_nats("products.updates", {
                    "type": "products_saved",
                    "count": len(products),
                    "message": f"Сохранено {len(products)} товаров в БД",
                    "products": saved_products[:10]
                })
                
            except Exception as e:
                await session.rollback()
                print(f"Ошибка при сохранении в БД: {e}")
                # Публикуем ошибку в NATS
                await publish_to_nats("products.updates", {
                    "type": "error",
                    "message": f"Ошибка при сохранении в БД: {str(e)}"
                })
    
    def save_products_to_db(self, products: list[Product]):
        """Синхронная обертка для сохранения в БД"""
        def run_async():
            """Запускаем асинхронную функцию в отдельном потоке"""
            new_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(new_loop)
            try:
                new_loop.run_until_complete(self._save_products_async(products))
            finally:
                new_loop.close()
        
        try:
            thread = threading.Thread(target=run_async)
            thread.start()
            thread.join()
        except Exception as e:
            print(f"Ошибка при запуске сохранения в БД: {e}")