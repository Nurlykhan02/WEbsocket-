from fastapi import WebSocket
from typing import Dict
import json



class WebSocketController:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, username: str):
        await websocket.accept()
        self.active_connections[username] = websocket
        print(f"WebSocket connected for user: {username}")

    async def disconnect(self, username):
        connection = self.active_connections.get(username)
        if connection:
                await connection.close()
                del self.active_connections[username]
                print(f"WebSocket disconnected for user: {username}")

    async def broadcast_message(self, message: dict):
        json_message = json.dumps(message) 

        for connection in self.active_connections.values():
            await connection.send_text(json_message)

    async def send_message(self, username: str, message: dict):
        json_message = json.dumps(message) 
        if username in self.active_connections:
            await self.active_connections[username].send_text(json_message)
        else:
            print(f"User {username} not connected")
