# In-process pub/sub for the /disruptions/live websocket. Stands in for
# what the spec has RabbitMQ + Redis Pub/Sub doing -- fine for one
# process, wouldn't survive a restart or scale past a single worker.
# Same trade-off as line_status.py, just for push instead of state.

from __future__ import annotations

from fastapi import WebSocket


class Broadcaster:
    def __init__(self) -> None:
        self._connections: list[WebSocket] = []

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self._connections.append(ws)

    def disconnect(self, ws: WebSocket) -> None:
        if ws in self._connections:
            self._connections.remove(ws)

    async def broadcast(self, message: dict) -> None:
        dead = []
        for ws in self._connections:
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)
