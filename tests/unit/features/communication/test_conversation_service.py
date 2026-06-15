"""
RED tests for 500ms cooldown in ConversationService.

Spec scenarios:
  - Cooldown 500ms blocks consecutive messages <500ms from same user.
  - Cooldown does NOT block messages past 500ms window.
  - First message (no previous timestamp) passes through.
"""

import json
import time
from unittest.mock import MagicMock, patch

import pytest

from app.features.communication.conversation_service import ConversationService
from app.models.models import Customer, CustomerData


@pytest.fixture
def mock_db():
    """Mock DB session."""
    return MagicMock()


@pytest.fixture
def mock_customer_repo():
    """Mock CustomerRepository."""
    return MagicMock()


def make_customer(phone="573001234567", state=CustomerData.IDLE, data=None):
    """Helper to create a Customer with given conversation_data."""
    customer = Customer(
        id=1,
        phone_hash="mock_hash",
        phone_encrypted="mock_enc",
        name="Test User",
        business_id=1,
        conversation_state=state,
        conversation_data=data or "{}",
    )
    return customer


class TestCooldown:
    """RED: 500ms cooldown between messages from the same user."""

    def test_messages_within_cooldown_are_dropped(self, mock_db):
        """
        Scenario: Rapid consecutive messages from same user — cooldown blocks.

        GIVEN a customer whose last message was 300ms ago
        WHEN a new message arrives
        THEN the message is dropped (cooldown active, no handler called).
        """
        now = time.time()
        data = json.dumps({"_last_msg_ts": now - 0.3})  # 300ms ago
        customer = make_customer(data=data)

        # Mock the repo to return this customer
        with patch.object(ConversationService, "__init__", lambda self, *a, **kw: None):
            service = ConversationService.__new__(ConversationService)
            service.db = mock_db
            service.phone_number_id = "123456"
            service.business_id = 1
            service.customer_repo = MagicMock()
            service.customer_repo.get_by_phone.return_value = customer
            service.welcome_handler = MagicMock()
            service.booking_handler = MagicMock()
            service.query_handler = MagicMock()
            service.business_repo = MagicMock()
            business_mock = MagicMock()
            business_mock.ai_enabled = False
            service.business_repo.get_by_id.return_value = business_mock

            # Call handle_incoming_message — cooldown should block
            service.handle_incoming_message(
                from_number="573001234567",
                message_body="Hola",
                message_type="text",
            )

            # The message should have been DROPPED by cooldown.
            # welcome_handler.handle_message should NOT be called.
            service.welcome_handler.handle_message.assert_not_called()
            service.booking_handler.handle_message.assert_not_called()
            service.query_handler.handle_message.assert_not_called()

    def test_messages_outside_cooldown_are_processed(self, mock_db):
        """
        Scenario: Message outside cooldown window is processed normally.

        GIVEN a customer whose last message was 60s ago
        WHEN a new message arrives
        THEN the message is processed by the appropriate handler.
        """
        now = time.time()
        data = json.dumps({"_last_msg_ts": now - 60.0})  # 60s ago
        customer = make_customer(data=data, state=CustomerData.IDLE)

        with patch.object(ConversationService, "__init__", lambda self, *a, **kw: None):
            service = ConversationService.__new__(ConversationService)
            service.db = mock_db
            service.phone_number_id = "123456"
            service.business_id = 1
            service.customer_repo = MagicMock()
            service.customer_repo.get_by_phone.return_value = customer
            service.welcome_handler = MagicMock()
            service.booking_handler = MagicMock()
            service.query_handler = MagicMock()
            service.business_repo = MagicMock()
            business_mock = MagicMock()
            business_mock.ai_enabled = False
            service.business_repo.get_by_id.return_value = business_mock

            service.handle_incoming_message(
                from_number="573001234567",
                message_body="Hola",
                message_type="text",
            )

            # Cooldown should NOT block — welcome_handler is called (IDLE state, no AI)
            service.welcome_handler.handle_message.assert_called_once()

    def test_first_message_no_cooldown(self, mock_db):
        """
        Scenario: First message from user (no _last_msg_ts) passes through.

        GIVEN a customer with NO previous message timestamp
        WHEN a new message arrives
        THEN the message is processed normally.
        """
        customer = make_customer(data="{}")  # No _last_msg_ts

        with patch.object(ConversationService, "__init__", lambda self, *a, **kw: None):
            service = ConversationService.__new__(ConversationService)
            service.db = mock_db
            service.phone_number_id = "123456"
            service.business_id = 1
            service.customer_repo = MagicMock()
            service.customer_repo.get_by_phone.return_value = customer
            service.welcome_handler = MagicMock()
            service.booking_handler = MagicMock()
            service.query_handler = MagicMock()
            service.business_repo = MagicMock()
            business_mock = MagicMock()
            business_mock.ai_enabled = False
            service.business_repo.get_by_id.return_value = business_mock

            service.handle_incoming_message(
                from_number="573001234567",
                message_body="Hola",
                message_type="text",
            )

            # First message should always pass cooldown check
            service.welcome_handler.handle_message.assert_called_once()
