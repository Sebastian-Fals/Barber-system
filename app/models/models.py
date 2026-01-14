from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Enum, Boolean
from sqlalchemy.orm import relationship
from app.core.database import Base
import enum
from datetime import datetime

class AppointmentStatus(str, enum.Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"
    COMPLETED = "completed"

class Business(Base):
    __tablename__ = "businesses"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    phone_number_id = Column(String, unique=True, index=True, nullable=False)
    calendar_id = Column(String, nullable=True, comment="Master calendar for the business")
    
    # Hours (24h format integer) - DEPRECATED in favor of schedule, kept for backwards compat
    open_hour = Column(Integer, default=9)
    close_hour = Column(Integer, default=18)
    # JSON String: {"0": {"start": 9, "end": 18}, "1": ...} Where 0=Monday, 6=Sunday
    schedule = Column(String, default="{}")
    
    # Relationships
    barbers = relationship("Barber", back_populates="business")

class Barber(Base):
    __tablename__ = "barbers"

    id = Column(Integer, primary_key=True, index=True)
    business_id = Column(Integer, ForeignKey("businesses.id"))
    name = Column(String, index=True)
    phone = Column(String)
    calendar_id = Column(String, nullable=True, comment="Individual barber calendar")

    # Relationships
    business = relationship("Business", back_populates="barbers")
    appointments = relationship("Appointment", back_populates="barber")

class CustomerData(str, enum.Enum):
    # Helps prevent typos in state names
    IDLE = "IDLE"
    SELECT_SERVICE = "SELECT_SERVICE"
    SELECT_BARBER = "SELECT_BARBER"
    SELECT_DATE = "SELECT_DATE"
    SELECT_SLOT = "SELECT_SLOT"
    CONFIRM_BOOKING = "CONFIRM_BOOKING"

class Customer(Base):
    __tablename__ = "customers"

    id = Column(Integer, primary_key=True, index=True)
    phone = Column(String, unique=True, index=True)
    name = Column(String)
    
    # Conversation State Management
    conversation_state = Column(String, default=CustomerData.IDLE)
    # Storing temp data like {"selected_barber_id": 1, "selected_date": "2023-10-27"}
    # Using String for simplicity in SQLite (JSON in Postgres)
    conversation_data = Column(String, default="{}")
    
    # Relationships
    appointments = relationship("Appointment", back_populates="customer")

class Appointment(Base):
    __tablename__ = "appointments"

    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(Integer, ForeignKey("customers.id"))
    barber_id = Column(Integer, ForeignKey("barbers.id"))
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=False)
    status = Column(String, default=AppointmentStatus.PENDING)
    google_event_id = Column(String, nullable=True)
    
    # Notification Status
    reminded_24h = Column(Boolean, default=False)
    reminded_1h = Column(Boolean, default=False)

    # Relationships
    customer = relationship("Customer", back_populates="appointments")
    barber = relationship("Barber", back_populates="appointments")

class ProcessedMessage(Base):
    __tablename__ = "processed_messages"

    id = Column(Integer, primary_key=True, index=True)
    message_id = Column(String, unique=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
