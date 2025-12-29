from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import time
import json
import nats

from app.database import engine
from app.models import TaskModel, ProductModel  # Импортируем модели
from sqlmodel import SQLModel  # Импортируем SQLModel напрямую
from app.routers import tasks, parser, products
from app.services.websocket_service import manager_ws
from app.scheduler import start_scheduler, shutdown_scheduler

from app.services.telegram_service import init_telegram_bot

app = FastAPI(
    title="TODOAPI",
    version="1.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"]
)

@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    duration = time.time() - start_time
    print(f"Request: {request.method} {request.url} - {duration:.3f} sec")
    return response

# Подключение роутеров
app.include_router(tasks.router)
app.include_router(parser.router)
app.include_router(products.router) 

@app.on_event("startup")
async def on_startup():
    # Создание таблиц БД
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    await init_telegram_bot()

    # NATS подключение
    global nc
    nc = await nats.connect("nats://127.0.0.1:4222")
    from app.services.parser_service import set_nats_connection
    set_nats_connection(nc)
    
    async def message_handler(msg):
        data = msg.data.decode()
        print(f"NATS msg: {data}")
        await manager_ws.broadcast(data)
    
    await nc.subscribe("products.updates", cb=message_handler)
    await nc.publish("products.updates", json.dumps({"type": "system", "message": "NATS подключен"}, ensure_ascii=False).encode())
    
    # Запуск планировщика
    await start_scheduler()

@app.on_event("shutdown")
async def on_shutdown():
    await shutdown_scheduler()

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager_ws.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            print(data)
            await manager_ws.handle(data, websocket)
    except WebSocketDisconnect:
        await manager_ws.disconnect(websocket)