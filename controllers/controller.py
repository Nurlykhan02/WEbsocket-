from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session
from sqlalchemy import not_
from database.session import get_db
from models.models import Payment,Users
from models.schemas import User, ManagerUsername, StatusUpdate, PaymentCreate, TelegramUpdate,PaymentValue, StatisticDates
from sqlalchemy import inspect, func
from jose import jwt
from datetime import datetime, timedelta
from typing import Optional, List
from controllers.controllersocket import WebSocketController
from controllers.config import TELEGRAM_TOKEN
import requests
import json
import aiohttp

SECRET_KEY = ""
ALGORITHM = ""
ACCESS_TOKEN_EXPIRE_MINUTES = 1440


class OrdersController:
    def __init__(self, websockets: WebSocketController):
        self.orders = APIRouter()
        self.websockets = websockets 
        self.inspector = inspect(Payment)
        self.columns = self.inspector.columns

        self.orders.add_api_route("/get_payments", self.get_payments, methods=['POST'])
        self.orders.add_api_route("/update_status", self.status_update, methods=['POST'])
        self.orders.add_api_route("/create_payment", self.create_payment, methods=['POST'])
        self.orders.add_api_route("/update_telegram_status", self.update_telegram_status, methods=['POST'])
        self.orders.add_api_route("/search_payment", self.search_payment, methods=['POST'])
       

    async def get_payments(self, username: ManagerUsername, db: Session = Depends(get_db)):
        role = db.query(Users.role).filter(Users.username == username.username).scalar()
        sorted_dict = {}
        
        if role == 'admin':
            payments = db.query(Payment).all()   
        else:
            payments = db.query(Payment).filter(
                (Payment.manager.is_(None)) | (Payment.manager == username.username) 
            )      
            
        payment_dicts = [
            {
                column.name: getattr(payment, column.name).strftime("%Y-%m-%d %H:%M:%S") if column.name == 'created_time' else getattr(payment, column.name)
                for column in self.columns
            }
            for payment in payments
        ]

        for payment_dict in payment_dicts:
            is_paid = payment_dict['is_paid']
            key = is_paid if is_paid is not None else 'None'
            if key not in sorted_dict:
                sorted_dict[key] = []

            sorted_dict[key].append(payment_dict)
        
        for key, array in sorted_dict.items():
            array.reverse()
            
        return sorted_dict
    
    async def search_payment(self, paymentValue: PaymentValue, db: Session = Depends(get_db)):
        return db.query(Payment).filter(
            (Payment.phone_number.like(f'%{paymentValue.paymentValue}%')) |
            (Payment.id.like(f'%{paymentValue.paymentValue}%')) |
            (Payment.name.like(f'%{paymentValue.paymentValue}%'))
        ).all()

    async def status_update(self, payment: StatusUpdate, db: Session = Depends(get_db)):
        paymentOne = db.query(Payment).filter(Payment.id == payment.id).first()
        if paymentOne:
            paymentOne.manager = payment.username
            paymentOne.is_paid = payment.type
            db.commit()

            payment_dict = {
                        'type':'statusUpdate',
                        'id': paymentOne.id,
                        'amount': paymentOne.amount,
                        'created_time': paymentOne.created_time.strftime("%Y-%m-%d %H:%M:%S"),
                        'is_paid': paymentOne.is_paid,
                        'manager': paymentOne.manager,
                        'name': paymentOne.name,
                        'phone_number': paymentOne.phone_number,
                        'username': paymentOne.username,
                        'CHATID':paymentOne.CHATID
                    }
        
            
            await self.send_notification(payment)
            await self.websockets.broadcast_message(payment_dict)
            return {"message": "Успешно"}
        else:
            raise ValueError("Платеж с указанным ID не найден")
    
    async def create_payment(self, payment: PaymentCreate, db: Session = Depends(get_db)):
        existing_payment = db.query(Payment).filter(Payment.id == payment.id).first()
        if existing_payment:
           
            db.delete(existing_payment)
            db.commit()
        
        new_payment = Payment(
            CHATID=payment.chatid,
            username=payment.username,
            phone_number=payment.phone_number,
            created_time=payment.created_time.strftime("%Y-%m-%d %H:%M:%S"),
            name=payment.name,
            id=payment.id,
            is_paid='Новый заказ',
            amount=payment.amount
        )
       
        db.add(new_payment)
        db.commit()
        
        await self.websockets.broadcast_message({
            'new_payment': {
                'id': new_payment.id,
                'amount': new_payment.amount,
                'name': new_payment.name,
                'phone_number': new_payment.phone_number,
                'username': new_payment.username,
                'created_time': new_payment.created_time.strftime("%Y-%m-%d %H:%M:%S"),
                'is_paid': new_payment.is_paid,
                'CHATID': new_payment.CHATID
            }
        })
        
        await self.update_payments_intime(db=db)
         
         
        return {"message": "Платеж успешно создан"}
        
        

    async def update_telegram_status(self, payment: TelegramUpdate, db: Session = Depends(get_db)):
        paymentOne = db.query(Payment).filter(Payment.id == payment.id).first()
        if paymentOne:
            paymentOne.is_paid = payment.new_status
            db.commit()

            payment_dict = {
                        'type':'statusUpdate',
                        'id': paymentOne.id,
                        'amount': paymentOne.amount,
                        'created_time': paymentOne.created_time.strftime("%Y-%m-%d %H:%M:%S"),
                        'is_paid': paymentOne.is_paid,
                        'manager': paymentOne.manager,
                        'name': paymentOne.name,
                        'phone_number': paymentOne.phone_number,
                        'username': paymentOne.username,
                        'CHATID':paymentOne.CHATID
                    }


        await self.websockets.broadcast_message(payment_dict)


    async def send_notification(self, data: StatusUpdate):
        try:
            url = f'https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage'
            text = f"Статус заказа №{data.id} - '{data.type}'"

            keyboard = {
                'inline_keyboard': [
                    [{'text': 'При получении', 'callback_data': f'by_receipt_{data.id}_{data.type}'}],
                ]
            }

            params = {
                'chat_id': data.chatid,
                'text': text,
                'reply_markup': json.dumps(keyboard)
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(url, params=params) as response:
                    response.raise_for_status()

                    if data.type == 'Отправлен' or data.type == 'Оплачен':
                        params = {
                            'chat_id': 326615796,
                            'text': text
                        }
                        async with session.post(url, params=params) as second_response:
                            second_response.raise_for_status()
        except aiohttp.ClientResponseError as e:
            raise HTTPException(status_code=401, detail="Ошибка при обновлении статуса")
        except Exception as e:
            raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")
        
        
   
    async def update_order_statuses(self, order_ids: List[int],orderType: str, db: Session):
        orders = db.query(Payment).filter(Payment.id.in_(order_ids), Payment.is_paid == orderType).all()
        status_mapping = {
            'В ожидании': 'Не оплачен',
            'Отправлен': 'В ожидании'
        }

        status_to_change = status_mapping.get(orderType)
        for order in orders:
            order.is_paid = status_to_change

            payment_dict = {
                'type': 'statusUpdate',
                'id': order.id,
                'amount': order.amount,
                'created_time': order.created_time.strftime("%Y-%m-%d %H:%M:%S"),
                'is_paid': status_to_change,
                'manager': order.manager,
                'name': order.name,
                'phone_number': order.phone_number,
                'username': order.username,
                'CHATID': order.CHATID
            }
            await self.websockets.broadcast_message(payment_dict)

        try:
            db.commit()
        except Exception as e:
            db.rollback()
            raise e


    async def update_payments_intime(self, db: Session = Depends(get_db)):
        current_time = datetime.now() - timedelta(days=1)
        order_ids_to_update_waiting = [order_id for (order_id,) in db.query(Payment.id).filter(Payment.created_time <= current_time, Payment.is_paid == "В ожидании").all()]
        
        
        fifteen_minutes_ago = datetime.now() - timedelta(minutes=60)
        sent_orders_ids = [order_id for (order_id,) in db.query(Payment.id).filter(Payment.created_time <= fifteen_minutes_ago, Payment.is_paid == "Отправлен").all()]
        
        await self.update_order_statuses(order_ids_to_update_waiting, 'В ожидании', db)
        await self.update_order_statuses(sent_orders_ids, 'Отправлен', db)


class UserController:
    def __init__(self):
        self.users = APIRouter()
        self.inspector = inspect(Users)
        self.columns = self.inspector.columns

        self.users.add_api_route("/login", self.login, methods=['POST'])
        self.users.add_api_route("/get_users", self.get_users, methods=['GET'])
        self.users.add_api_route("/add_user", self.add_user, methods=['POST'])
        self.users.add_api_route("/delete_user/{usernameToDelete}", self.delete_user, methods=['DELETE'])
    
    async def login(self, user: User, db: Session = Depends(get_db)):
        db_user = db.query(Users).filter(Users.username == user.username).first()

        if not db_user:
            raise HTTPException(status_code=401, detail="Неверные учетные данные")
        
        if db_user.password != user.password:
             raise HTTPException(status_code=401, detail="Неверные учетные данные")

        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = self.create_access_token(data={'sub': db_user.username}, expires_delta=access_token_expires, login=db_user.username, id=db_user.id, role=db_user.role)
        return {"message": "Вход выполнен успешно", 'token': access_token, 'role': db_user.role, 'username': db_user.username}

    def create_access_token(self, data: dict, expires_delta: timedelta, login: Optional[str] = None, id: Optional[str] = None, role: Optional[str] = None):
        to_encode = data.copy()
        expire = datetime.utcnow() + expires_delta
        to_encode.update({'exp': expire})
        if login and id:
            to_encode.update({'login': login, 'id': id, 'role': role})
        encoded_jwt = jwt.encode(to_encode,SECRET_KEY,algorithm=ALGORITHM)
        return encoded_jwt
    
    async def get_users(self, db: Session = Depends(get_db)):
        db_users = db.query(Users.username).all()
        users_list = [user[0] for user in db_users]  
        return users_list

    async def add_user(self,user:User, db: Session = Depends(get_db)):
        new_user =Users(
            username = user.username,
            password = user.password,
            role = 'operator'
        ) 
        db.add(new_user)
        db.commit()

    async def delete_user(self, usernameToDelete: str, db: Session = Depends(get_db)):
        user = db.query(Users).filter(Users.username == usernameToDelete).first()
        if user:
            db.delete(user)
            db.commit()
            return {"message": "User deleted successfully"}
        else:
            raise HTTPException(status_code=404, detail="User not found")
            
            
class StatisticController:
    def __init__(self):
        self.statistic =  APIRouter()
        self.statistic.add_api_route("/statistics", self.get_statistic, methods=['POST'])

    async def get_statistic(self, dates: StatisticDates, db: Session = Depends(get_db)):
        managerResult = db.query(
            Payment.manager,
            func.sum(func.if_(Payment.is_paid == 'Отправлен', 1, 0)).label('Отправлен'),
            func.sum(func.if_(Payment.is_paid == 'В ожидании', 1, 0)).label('В_ожидании'),
            func.sum(func.if_(Payment.is_paid == 'При получении', 1, 0)).label('При_получении'),
            func.sum(func.if_(Payment.is_paid == 'Оплачен', 1, 0)).label('Оплачен'),
            func.sum(func.if_(Payment.is_paid == 'Не оплачен', 1, 0)).label('Не_оплачен'),
            func.sum(func.if_(Payment.is_paid == 'Нет каспи', 1, 0)).label('Нет_каспи'),
        ).filter(
            Payment.created_time >= dates.startDate,
            Payment.created_time <= dates.endDate
        ).group_by(Payment.manager).all()
        
        operatorResult = db.query(
            Payment.username,
            func.sum(func.if_(Payment.is_paid == 'Отправлен', 1, 0)).label('Отправлен'),
            func.sum(func.if_(Payment.is_paid == 'В ожидании', 1, 0)).label('В_ожидании'),
            func.sum(func.if_(Payment.is_paid == 'При получении', 1, 0)).label('При_получении'),
            func.sum(func.if_(Payment.is_paid == 'Оплачен', 1, 0)).label('Оплачен'),
            func.sum(func.if_(Payment.is_paid == 'Не оплачен', 1, 0)).label('Не_оплачен'),
            func.sum(func.if_(Payment.is_paid == 'Нет каспи', 1, 0)).label('Нет_каспи'),
        ).filter(
            Payment.created_time >= dates.startDate,
            Payment.created_time <= dates.endDate
        ).group_by(Payment.username).all()


        manager_result_dicts = [dict(manager=row[0], Отправлен=row[1], В_ожидании=row[2], При_получении=row[3], Оплачен=row[4], Не_оплачен=row[5], Нет_каспи=row[6]) for row in managerResult]
        operator_result_dicts = [dict(operator=row[0], Отправлен=row[1], В_ожидании=row[2], При_получении=row[3], Оплачен=row[4], Не_оплачен=row[5], Нет_каспи=row[6]) for row in operatorResult]

        data = {'managerResult':manager_result_dicts, 'operatorResult': operator_result_dicts}
        return data