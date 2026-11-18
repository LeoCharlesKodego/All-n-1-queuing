"""WebSocket fan-out for live queue updates."""
import asyncio
import json

from fastapi import WebSocket


class Manager:
    def __init__(self) -> None:
        self.clients: list[WebSocket] = []
        self.loop: asyncio.AbstractEventLoop | None = None

    def set_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self.loop = loop

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.clients.append(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        if websocket in self.clients:
            self.clients.remove(websocket)

    async def broadcast(self, message: dict) -> None:
        payload = json.dumps(message, default=str)
        dead = []
        for client in list(self.clients):
            try:
                await client.send_text(payload)
            except Exception:
                dead.append(client)
        for client in dead:
            self.disconnect(client)

    def send(self, message: dict) -> None:
        if not self.loop or not self.clients:
            return
        asyncio.run_coroutine_threadsafe(self.broadcast(message), self.loop)


manager = Manager()


def publish(message: dict) -> None:
    manager.send(message)
