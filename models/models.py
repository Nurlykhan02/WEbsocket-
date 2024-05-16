from sqlalchemy.orm import declarative_base
from sqlalchemy import Column, Integer, VARCHAR, DATETIME

Base = declarative_base()

class Payment(Base):

    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, index=True)
    amount = Column(Integer, index=True)
    name = Column(VARCHAR(100), index=True)
    username = Column(VARCHAR(100), index=True)
    created_time = Column(DATETIME, index=True)
    manager = Column(VARCHAR(50), index=True)
    is_paid = Column(VARCHAR(50), index=True)
    CHATID = Column(VARCHAR(50), index=True)
    phone_number = Column(VARCHAR(20), index=True)


class Users(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(VARCHAR(50), index=True)
    password = Column(VARCHAR(255), index=True)
    role = Column(VARCHAR(50), index=True)