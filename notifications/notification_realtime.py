"""
PRAHARI-AI Real-Time WebSocket Delivery Manager
Manages authenticated WebSocket connections, per-user session tracking,
connection limiting, ping/pong heartbeats, and non-blocking asynchronous delivery.
"""

import asyncio
import json
import logging
from typing import Dict, Set, Optional, Any, List
from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger("PRAHARI-NOTIF-WS")

from starlette.websockets import WebSocketState

MAX_CONNECTIONS_PER_USER = 5


class WebSocketManager:
    def __init__(self):
        # user_id -> set of active WebSockets
        self._user_connections: Dict[int, Set[WebSocket]] = {}
        # websocket -> user_id
        self._socket_to_user: Dict[WebSocket, int] = {}
        self._lock = asyncio.Lock() if asyncio.get_event_loop().is_running() else None
        self._main_loop: Optional[asyncio.AbstractEventLoop] = None

    def set_loop(self, loop: asyncio.AbstractEventLoop):
        """Sets reference to main running event loop for threadsafe dispatches."""
        self._main_loop = loop

    def get_active_user_count(self) -> int:
        return len(self._user_connections)

    def get_total_connections(self) -> int:
        return len(self._socket_to_user)

    async def connect(self, websocket: WebSocket, user_id: int) -> bool:
        """Register a new authenticated WebSocket session for a user."""
        user_conns = self._user_connections.setdefault(user_id, set())

        # Clean out any dead/disconnected sockets before checking limit
        dead = [ws for ws in list(user_conns) if getattr(ws, "client_state", None) == WebSocketState.DISCONNECTED]
        for d in dead:
            self.disconnect(d)

        # Connection limiting per user
        if len(user_conns) >= MAX_CONNECTIONS_PER_USER:
            logger.warning(f"[NotifWS] Max connections ({MAX_CONNECTIONS_PER_USER}) exceeded for user {user_id}. Rejecting.")
            await websocket.close(code=1008, reason="Connection limit exceeded")
            return False

        user_conns.add(websocket)
        self._socket_to_user[websocket] = user_id
        logger.info(f"[NotifWS] User {user_id} connected. Active user sockets: {len(user_conns)}")
        return True

    def disconnect(self, websocket: WebSocket):
        """Cleanly unregister a disconnected WebSocket session."""
        user_id = self._socket_to_user.pop(websocket, None)
        if user_id and user_id in self._user_connections:
            self._user_connections[user_id].discard(websocket)
            if not self._user_connections[user_id]:
                self._user_connections.pop(user_id, None)
            logger.info(f"[NotifWS] User {user_id} disconnected. Remaining user sessions: {len(self._user_connections.get(user_id, []))}")

    async def send_to_user(self, user_id: int, payload: Dict[str, Any]):
        """Directly deliver a JSON payload to all active sessions of a specific user."""
        sockets = list(self._user_connections.get(user_id, []))
        if not sockets:
            return

        json_data = json.dumps(payload)
        dead_sockets = []
        for ws in sockets:
            try:
                if getattr(ws, "client_state", None) == WebSocketState.CONNECTED:
                    await ws.send_text(json_data)
                else:
                    dead_sockets.append(ws)
            except Exception as ex:
                logger.warning(f"[NotifWS] Error sending to socket for user {user_id}: {ex}")
                dead_sockets.append(ws)

        for dead in dead_sockets:
            self.disconnect(dead)

    async def broadcast_to_users(self, user_ids: List[int], payload: Dict[str, Any]):
        """Broadcast payload to all provided user IDs."""
        tasks = [self.send_to_user(uid, payload) for uid in user_ids]
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    def dispatch_payload_threadsafe(self, user_ids: List[int], payload: Dict[str, Any]):
        """
        Thread-safe entry point for camera workers and background threads.
        Never blocks the caller.
        """
        try:
            loop = self._main_loop
            if loop and loop.is_running():
                asyncio.run_coroutine_threadsafe(self.broadcast_to_users(user_ids, payload), loop)
            else:
                try:
                    curr_loop = asyncio.get_running_loop()
                    curr_loop.create_task(self.broadcast_to_users(user_ids, payload))
                except RuntimeError:
                    pass
        except Exception as ex:
            logger.error(f"[NotifWS] Failed to dispatch threadsafe notification: {ex}")


ws_manager = WebSocketManager()
