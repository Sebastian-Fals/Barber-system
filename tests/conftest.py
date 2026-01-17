import unittest
from unittest.mock import MagicMock

import pytest
from sqlalchemy.orm import Session

from app.models.models import Business, Customer
from app.repositories.appointment_repository import AppointmentRepository
from app.repositories.barber_repository import BarberRepository
from app.repositories.business_repository import BusinessRepository
from app.repositories.customer_repository import CustomerRepository


@pytest.fixture
def db_session():
    """Mock database session"""
    return MagicMock(spec=Session)


@pytest.fixture
def mock_whatsapp():
    with unittest.mock.patch("app.services.whatsapp_service.whatsapp_service") as mock:
        yield mock


@pytest.fixture
def mock_llm():
    with unittest.mock.patch("app.services.llm_service.llm_service") as mock:
        yield mock


@pytest.fixture
def customer_repo(db_session):
    repo = MagicMock(spec=CustomerRepository)
    repo.db = db_session
    return repo


@pytest.fixture
def appointment_repo(db_session):
    repo = MagicMock(spec=AppointmentRepository)
    repo.db = db_session
    return repo


@pytest.fixture
def barber_repo(db_session):
    repo = MagicMock(spec=BarberRepository)
    repo.db = db_session
    return repo


@pytest.fixture
def business_repo(db_session):
    repo = MagicMock(spec=BusinessRepository)
    repo.db = db_session
    return repo


@pytest.fixture
def sample_customer():
    return Customer(id=1, phone="573001234567", name="Test User", conversation_state="IDLE")


@pytest.fixture
def sample_business():
    return Business(id=1, name="Test Barber", phone_number_id="12345")
