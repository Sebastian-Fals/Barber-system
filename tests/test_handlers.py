from unittest.mock import MagicMock, call

import pytest

from app.models.models import Customer, CustomerData
from app.services.handlers.booking_handler import BookingHandler
from app.services.handlers.query_handler import QueryHandler
from app.services.handlers.welcome_handler import WelcomeHandler


def test_welcome_handler_menu(db_session, mock_whatsapp, customer_repo):
    handler = WelcomeHandler(db_session, "123")
    handler.customer_repo = customer_repo

    customer = Customer(id=1, phone="57300123", name="Test", conversation_state="IDLE")

    # Test handle_message
    handler.handle_message(customer, "hola")
    mock_whatsapp.send_interactive_button.assert_called()


def test_booking_handler_flow(db_session, mock_whatsapp, customer_repo, barber_repo):
    handler = BookingHandler(db_session, "123")
    handler.customer_repo = customer_repo
    handler.barber_repo = barber_repo

    customer = Customer(id=1, phone="57300123", conversation_state="SELECT_BARBER")

    # Mock Barber List
    mock_barber = MagicMock()
    mock_barber.id = 1
    mock_barber.name = "Joe"
    barber_repo.get_all.return_value = [mock_barber]

    # 1. Start Flow (Usually triggered by WelcomeHandler, but if we call handle_message in SELECT_BARBER)
    # The handler expects interactive inputs mostly.
    # If we are in SELECT_BARBER, and user sends text? Handler might show list again?
    # BookingHandler.handle_message for text mostly sends error/prompt again.
    # Let's test handle_interactive for selecting a barber.

    handler.handle_interactive(customer, "barber_1", {})

    assert customer.conversation_state == CustomerData.SELECT_DATE
    mock_whatsapp.send_interactive_button.assert_called()  # Date prompt


def test_query_handler_intent(db_session, mock_whatsapp, mock_llm, customer_repo):
    handler = QueryHandler(db_session, "123")
    handler.customer_repo = customer_repo

    customer = Customer(id=1, phone="57300123", conversation_state="IDLE")

    # Mock LLM
    mock_llm.analyze_message.return_value = {"intent": "BOOKING", "reply": "Sure"}

    handler.handle_message(customer, "Quiero una cita")

    assert customer.conversation_state == CustomerData.SELECT_BARBER  # Should transition to booking
    mock_whatsapp.send_interactive_button.assert_called()  # Should send barber list/welcome booking
