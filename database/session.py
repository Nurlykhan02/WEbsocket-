from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

hostname = ""
database_name = ""
username = ""
password = ""


SQLALCHEMY_DATABASE_URL = f"mysql+mysqlconnector://{username}:{password}@{hostname}/{database_name}"

engine = create_engine(SQLALCHEMY_DATABASE_URL)

SessionLocal = sessionmaker(autoflush = False, autocommit = False, bind = engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()