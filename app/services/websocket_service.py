from fastapi import WebSocket
import asyncio
import threading


class ConnectionManager:
    def __init__(self):
        self.active_connection: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connection.append(websocket)

    async def handle(self, data, websocket):
        if data == "spec":   
            await websocket.send_text("Spec ok!")
        elif data == "close":
            await self.disconnect(websocket)

    async def disconnect(self, websocket: WebSocket):
        await websocket.close()
        self.active_connection.remove(websocket)

    async def broadcast(self, data: str):
        for ws in self.active_connection:
            await ws.send_text(data)


manager_ws = ConnectionManager()

def send_ws_notification(message: str):
    def run_async():
        new_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(new_loop)
        try:
            new_loop.run_until_complete(manager_ws.broadcast(message))
        finally:
            new_loop.close()
    thread = threading.Thread(target=run_async)
    thread.start()