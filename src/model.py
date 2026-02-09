from datetime import datetime
from sqlalchemy import Column, Integer, ForeignKey, Date, text, String, Boolean, DateTime
from database import Base
from sqlalchemy.sql import func

class Users(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key = True, index = True)
    email = Column(String(200), unique = True, nullable = False)
    username = Column(String(45), unique = True, nullable = False)
    hashed_password = Column(String(200), nullable = False)
    role = Column(String, default="user")


class Hosts(Base):
    __tablename__ = "hosts"

    id = Column(Integer, primary_key = True, index = True)
    company_name = Column(String(100), nullable = False)
    email = Column(String(200), unique=True, nullable = False)
    is_fee_paid = Column(Boolean, default = False)
    hashed_password = Column(String(200), nullable = False)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True)
    

class HostPromotions(Base):
    __tablename__ = "host_promotions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    amount = Column(Integer)
    status = Column(String)
    created_at = Column(DateTime, server_default = func.now())


class Events(Base):
    __tablename__ = "events"

    id = Column(Integer, primary_key = True, index = True)
    title = Column(String(200), nullable = False)
    host_id = Column(Integer, ForeignKey("hosts.id"), nullable = False)
    venue = Column(String(100))
    date = Column(Date, nullable = False)
    seats = Column(Integer, nullable = False)
    available_seats = Column(Integer, nullable = False)
    ticket_price = Column(Integer, nullable=False, default=100)


class BookingPayments(Base):
    __tablename__ = "booking_payments"

    id = Column(Integer, primary_key = True, index = True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable = False)
    booking_id = Column(Integer, ForeignKey("bookings.id"), nullable = False)
    amount = Column(Integer , nullable = False)
    status = Column(String(20), nullable = False)
    created_at = Column(DateTime, server_default = func.now())


class HostingPayments(Base):
    __tablename__ = "hosting_payments"

    id = Column(Integer, primary_key = True,index = True)
    host_id = Column(Integer, ForeignKey("hosts.id"), nullable = False)
    amount = Column(Integer, nullable = False)
    status = Column(String(20), nullable = False)
    created_at = Column(DateTime, server_default = func.now())


class Bookings(Base):
    __tablename__ = "bookings"

    id = Column(Integer, primary_key = True, index = True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable = False)
    event_id = Column(Integer, ForeignKey("events.id"), nullable = False)
    ticket_count = Column(Integer, nullable = False)


class Wallets(Base):
    __tablename__ = "wallets"

    id = Column(Integer, primary_key = True, index = True)
    owner_type = Column(String(10))
    owner_id = Column(Integer, nullable = False)
    balance = Column(Integer, server_default=text("0"))