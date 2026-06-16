import enum
from datetime import datetime

import pytz
from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import relationship

from app.core.database import Base, EncryptedString, UTCDateTime
from app.core.security import hash_value


class AppointmentStatus(str, enum.Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"
    COMPLETED = "completed"


class Business(Base):
    __tablename__ = "businesses"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    instance_name = Column(String, unique=True, index=True, nullable=False)
    instance_apikey = Column(EncryptedString, nullable=False)
    phone = Column(EncryptedString, nullable=True, comment="Public contact number")
    calendar_id = Column(EncryptedString, nullable=True, comment="Master calendar for the business")
    ai_enabled = Column(Boolean, default=True)  # New flag for Hybrid Flow

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
    phone = Column(EncryptedString, nullable=True)  # Optional, for notifications
    calendar_id = Column(EncryptedString, nullable=True, comment="Individual barber calendar")

    # Relationships
    business = relationship("Business", back_populates="barbers")
    appointments = relationship("Appointment", back_populates="barber")


class Service(Base):
    __tablename__ = "services"

    id = Column(Integer, primary_key=True, index=True)
    business_id = Column(Integer, ForeignKey("businesses.id"), nullable=False)
    name = Column(String, nullable=False)
    duration_minutes = Column(Integer, default=60)

    business = relationship("Business")


class CustomerData(str, enum.Enum):
    # Helps prevent typos in state names
    IDLE = "IDLE"
    SELECT_SERVICE = "SELECT_SERVICE"
    SELECT_BARBER = "SELECT_BARBER"
    SELECT_DATE = "SELECT_DATE"
    SELECT_SLOT = "SELECT_SLOT"
    CONFIRM_BOOKING = "CONFIRM_BOOKING"
    WAITING_NAME = "WAITING_NAME"


class Customer(Base):
    __tablename__ = "customers"
    __table_args__ = (UniqueConstraint("phone_hash", "business_id", name="uq_customer_phone_business"),)

    id = Column(Integer, primary_key=True, index=True)
    phone_hash = Column(String, index=True)
    phone_encrypted = Column(EncryptedString, nullable=False)
    name = Column(EncryptedString)
    business_id = Column(Integer, ForeignKey("businesses.id"), nullable=False)

    # Conversation State Management
    conversation_state = Column(String, default=CustomerData.IDLE)
    # Storing temp data like {"selected_barber_id": 1, "selected_date": "2023-10-27"}
    # Using String for simplicity in SQLite (JSON in Postgres)
    conversation_data = Column(String, default="{}")

    # Relationships
    business = relationship("Business")
    appointments = relationship("Appointment", back_populates="customer")

    @property
    def phone(self):
        return self.phone_encrypted

    @phone.setter
    def phone(self, value):
        self.phone_encrypted = value
        self.phone_hash = hash_value(value)


class Appointment(Base):
    __tablename__ = "appointments"

    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(Integer, ForeignKey("customers.id"))
    barber_id = Column(Integer, ForeignKey("barbers.id"))
    business_id = Column(Integer, ForeignKey("businesses.id"), nullable=False)
    start_time = Column(UTCDateTime, nullable=False)
    end_time = Column(UTCDateTime, nullable=False)
    status = Column(String, default=AppointmentStatus.PENDING)
    # Dual Calendar Sync
    google_barber_event_id = Column(String, nullable=True)
    google_business_event_id = Column(String, nullable=True)

    # Notification Status
    reminded_24h = Column(Boolean, default=False)
    reminded_1h = Column(Boolean, default=False)

    # Relationships
    customer = relationship("Customer", back_populates="appointments")
    barber = relationship("Barber", back_populates="appointments")
    business = relationship("Business")


class ProcessedMessage(Base):
    __tablename__ = "processed_messages"
    __table_args__ = (UniqueConstraint("message_id", "business_id", name="uq_processed_msg_business"),)

    id = Column(Integer, primary_key=True, index=True)
    message_id = Column(String, index=True)
    business_id = Column(Integer, ForeignKey("businesses.id"), nullable=False)
    created_at = Column(UTCDateTime, default=lambda: datetime.now(pytz.UTC))

    business = relationship("Business")


class ConversationHistory(Base):
    __tablename__ = "conversation_history"

    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), index=True)
    business_id = Column(Integer, ForeignKey("businesses.id"), nullable=False)
    role = Column(String)  # 'user' or 'assistant'
    message = Column(EncryptedString)  # Encrypted content
    created_at = Column(UTCDateTime, default=lambda: datetime.now(pytz.UTC))

    customer = relationship("Customer")
    business = relationship("Business")
