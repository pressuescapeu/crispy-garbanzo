from fastapi import WebSocket

class WSManager:
    def __init__(self):
        self.rooms: dict[str, list[WebSocket]] = {}

    async def connect(self, room_id: str, websocket: WebSocket):
        await websocket.accept()
        self.rooms.setdefault(room_id, []).append(websocket)

    def disconnect(self, room_id: str, websocket: WebSocket):
        if room_id in self.rooms:
            self.rooms[room_id].remove(websocket)
            if not self.rooms[room_id]:
                del self.rooms[room_id]

    async def broadcast(self, room_id: str, action: dict):
        """Broadcast action to all users in a room."""
        if room_id not in self.rooms:
            return

        # Send to all connected clients in this room
        disconnected = []
        for ws in self.rooms.get(room_id, []):
            try:
                await ws.send_json(action)
            except Exception as e:
                print(f"Failed to send to client: {e}")
                disconnected.append(ws)

        # Remove disconnected clients
        for ws in disconnected:
            self.disconnect(room_id, ws)
