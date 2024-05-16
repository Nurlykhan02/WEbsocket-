from fastapi import FastAPI, Depends,WebSocket, WebSocketDisconnect, BackgroundTasks
from sqlalchemy.orm import Session
from database.session import get_db
from fastapi.middleware.cors import CORSMiddleware
from controllers.controller import OrdersController, UserController,StatisticController
from controllers.controllersocket import WebSocketController
import asyncio
from datetime import timedelta
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_headers=["*"],
    allow_methods=["*"],
    allow_origins=["*"]
)
websockets_controller = WebSocketController()
paymentsController = OrdersController(websockets=websockets_controller)
userController = UserController()
statisticController = StatisticController()



@app.websocket("/ws/{username}")
async def websocket_endpoint(websocket: WebSocket, username: str):
    await websockets_controller.connect(websocket, username)
    try:
        while True:
            data = await websocket.receive_text()
            await websockets_controller.broadcast_message(data)
    except WebSocketDisconnect:
        pass  



app.include_router(paymentsController.orders,prefix='/v1')
app.include_router(userController.users, prefix='/v1')
app.include_router(statisticController.statistic, prefix='/v1')