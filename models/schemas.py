from pydantic import BaseModel
from fastapi import WebSocket
from datetime import datetime


class User(BaseModel):
    username: str
    password: str


class ManagerUsername(BaseModel):
    username: str


class StatusUpdate(BaseModel):
    id: int
    username: str
    type: str
    chatid: str

class PaymentCreate(BaseModel):
    id: int
    amount: int
    name: str
    phone_number: str
    username: str
    created_time: datetime
    chatid: str


class TelegramUpdate(BaseModel):
    prev_status: str
    new_status: str
    id: int


class PaymentValue(BaseModel):
    paymentValue: str


class StatisticDates(BaseModel):
    startDate: str
    endDate: str