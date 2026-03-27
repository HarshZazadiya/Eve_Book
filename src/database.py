from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
import os 

load_dotenv()
# engine = create_engine("postgresql://postgres:postgres@localhost:5433/EventBooking")
engine = create_engine(os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5433/EventBooking"))
SessionLocal = sessionmaker(
    autocommit = False,
    autoflush = False,
    bind = engine
)

Base = declarative_base()
