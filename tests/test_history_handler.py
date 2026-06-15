from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
import pytz

from app.services.handlers.query_handler import QueryHandler


@pytest.fixture
def mock_db():
    return MagicMock()


@pytest.fixture
def handler(mock_db):
    # Mock repositories init inside QueryHandler
    with patch("app.services.handlers.query_handler.CustomerRepository"), patch(
        "app.services.handlers.query_handler.BarberRepository"
    ), patch("app.services.handlers.query_handler.BusinessRepository"), patch(
        "app.services.handlers.query_handler.AppointmentRepository"
    ), patch(
        "app.services.handlers.query_handler.BookingService"
    ):
        h = QueryHandler(mock_db, "phone_id", 1)
        h.business = MagicMock(name="Biz")  # Mock business presence
        return h


def test_manage_history_expiration_purges_old(handler, mock_db):
    # Setup: Last msg was 25 hours ago
    old_msg = MagicMock()
    # ensure tz aware
    old_msg.created_at = datetime.now(pytz.UTC) - timedelta(hours=25)

    # query().filter().order_by().first()
    mock_db.query.return_value.filter.return_value.order_by.return_value.first.return_value = old_msg

    # Act
    handler._manage_history_expiration(1)

    # Assert
    # Verify delete called
    # logic: query(CH).filter(CH.customer_id).delete()
    # Note: query(...) creates a NEW Query object.
    # We need to ensure the delete call happens on a query object.

    # With MagicMock, checking if any delete() was called is usually enough or we check chaining.
    mock_db.query.return_value.filter.return_value.delete.assert_called()


def test_manage_history_expiration_keeps_recent(handler, mock_db):
    # Setup: Last msg was 1 hour ago
    recent_msg = MagicMock()
    recent_msg.created_at = datetime.now(pytz.UTC) - timedelta(hours=1)

    mock_db.query.return_value.filter.return_value.order_by.return_value.first.return_value = recent_msg

    # Act
    handler._manage_history_expiration(1)

    # Assert
    mock_db.query.return_value.filter.return_value.delete.assert_not_called()


def test_build_llm_context_fetches_history(handler, mock_db):
    customer = MagicMock(id=1, name="Test", conversation_state="IDLE")

    # Mock History
    h1 = MagicMock(role="user", message="Hi")
    h2 = MagicMock(role="assistant", message="Hello")

    # query().filter().order_by().limit().all()
    mock_db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [h1, h2]

    # Act
    ctx = handler._build_llm_context(customer)

    # Assert
    assert len(ctx["history"]) == 2
    assert ctx["history"][0]["role"] == "user"
    assert ctx["history"][1]["content"] == "Hello"
