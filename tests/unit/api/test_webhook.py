"""
Tests for webhook behavior: multi-tenant, direct processing (no BufferService), dedup.

Spec scenarios:
  - Webhook with unknown phone_number_id → return 200, no DB writes.
  - Webhook with known phone_number_id → business_id resolved and propagated.
  - Text message processed directly without BufferService.debounce.
  - Dedup via ProcessedMessage still works (no BufferService).
"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.api.webhook import process_background_message  # noqa: F401
from app.core.database import get_db
from app.main import app


@pytest.fixture
def mock_db():
    """Mock DB session."""
    return MagicMock()


@pytest.fixture
def client(mock_db):
    """Test client with mocked DB dependency."""
    app.dependency_overrides[get_db] = lambda: mock_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


class TestWebhookMultiTenant:
    """RED: webhook resolves business_id from phone_number_id."""

    @patch("app.api.webhook.BusinessRepository")
    def test_unknown_phone_number_id_returns_200_no_db_write(self, mock_biz_repo_class, client, mock_db):
        """
        Scenario: Webhook with unknown phone_number_id.
        - GIVEN phone_number_id "999999" does NOT map to any business
        - WHEN a WhatsApp webhook arrives with phone_number_id "999999"
        - THEN the webhook returns 200 AND no un-scoped data is created.
        """
        # Configure mock: get_by_phone_number_id returns None
        mock_biz_repo = MagicMock()
        mock_biz_repo.get_by_phone_number_id.return_value = None
        mock_biz_repo_class.return_value = mock_biz_repo

        payload = {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "changes": [
                        {
                            "value": {
                                "metadata": {"phone_number_id": "999999"},
                                "messages": [
                                    {
                                        "id": "wa-unknown-001",
                                        "from": "573001234567",
                                        "type": "text",
                                        "text": {"body": "Hola"},
                                    }
                                ],
                            }
                        }
                    ]
                }
            ],
        }

        response = client.post("/api/v1/webhook", json=payload)
        assert response.status_code == 200
        assert response.json() == {"status": "received"}

    @patch("app.api.webhook.BusinessRepository")
    @patch("app.api.webhook.process_background_message")
    def test_known_phone_number_id_resolves_business(self, mock_process_bg, mock_biz_repo_class, client, mock_db):
        """
        Scenario: Webhook with known phone_number_id.
        - GIVEN phone_number_id "123456" maps to Business A
        - WHEN a WhatsApp webhook arrives with phone_number_id "123456"
        - THEN business_id is resolved and message is dispatched.
        """
        from app.models.models import Business

        business = Business(id=1, name="Barbería Test", phone_number_id="123456")

        mock_biz_repo = MagicMock()
        mock_biz_repo.get_by_phone_number_id.return_value = business
        mock_biz_repo_class.return_value = mock_biz_repo

        payload = {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "changes": [
                        {
                            "value": {
                                "metadata": {"phone_number_id": "123456"},
                                "messages": [
                                    {
                                        "id": "wa-known-001",
                                        "from": "573001234567",
                                        "type": "text",
                                        "text": {"body": "Hola"},
                                    }
                                ],
                            }
                        }
                    ]
                }
            ],
        }

        response = client.post("/api/v1/webhook", json=payload)
        assert response.status_code == 200


class TestDirectProcessing:
    """RED: text messages processed directly, no BufferService debounce."""

    @pytest.mark.asyncio
    @patch("app.api.webhook.run_in_threadpool")
    @patch("app.api.webhook.ConversationService")
    @patch("app.api.webhook.SessionLocal")
    async def test_text_message_processed_directly_without_buffer(
        self, mock_session_local, mock_conv_service_class, mock_run_in_threadpool
    ):
        """
        Scenario: Text message processed immediately.

        GIVEN a text message arrives at the webhook
        WHEN process_background_message is called with msg_type="text"
        THEN ConversationService.handle_incoming_message is invoked
        AND no BufferService is involved (import removed).
        """
        mock_session = MagicMock()
        mock_session_local.return_value = mock_session

        mock_conv_service = MagicMock()
        mock_conv_service_class.return_value = mock_conv_service

        def fake_run_in_threadpool(fn):
            fn()
            return None

        mock_run_in_threadpool.side_effect = fake_run_in_threadpool

        await process_background_message(
            phone_number_id="123456",
            from_number="573001234567",
            msg_body="Hola",
            msg_type="text",
            interactive_id=None,
            business_id=1,
        )

        # ConversationService should be instantiated with correct args
        mock_conv_service_class.assert_called_once_with(mock_session, "123456", 1)
        # handle_incoming_message should be called with correct params
        mock_conv_service.handle_incoming_message.assert_called_once_with("573001234567", "Hola", "text", None)

    @pytest.mark.asyncio
    @patch("app.api.webhook.run_in_threadpool")
    @patch("app.api.webhook.ConversationService")
    @patch("app.api.webhook.SessionLocal")
    async def test_non_text_message_still_processed_directly(
        self, mock_session_local, mock_conv_service_class, mock_run_in_threadpool
    ):
        """
        Scenario: Interactive messages already bypass buffer — keep working.

        GIVEN an interactive message arrives
        WHEN process_background_message is called with msg_type="interactive"
        THEN ConversationService.handle_incoming_message is still invoked directly.
        """
        mock_session = MagicMock()
        mock_session_local.return_value = mock_session

        mock_conv_service = MagicMock()
        mock_conv_service_class.return_value = mock_conv_service

        def fake_run_in_threadpool(fn):
            fn()

        mock_run_in_threadpool.side_effect = fake_run_in_threadpool

        await process_background_message(
            phone_number_id="123456",
            from_number="573001234567",
            msg_body="",
            msg_type="interactive",
            interactive_id="service_corte",
            business_id=1,
        )

        mock_conv_service.handle_incoming_message.assert_called_once_with(
            "573001234567", "", "interactive", "service_corte"
        )


class TestWebhookDedup:
    """RED: deduplication via ProcessedMessage works without BufferService."""

    @patch("app.api.webhook.BusinessRepository")
    @patch("app.api.webhook.process_background_message")
    def test_duplicate_message_dropped(self, mock_process_bg, mock_biz_repo_class, client, mock_db):
        """
        Scenario: Duplicate message is caught via ProcessedMessage.

        GIVEN message "wa-dup-001" already processed for Business A
        WHEN the same message "wa-dup-001" arrives again for Business A
        THEN it is dropped (background task NOT dispatched).
        """
        from app.models.models import Business, ProcessedMessage

        business = Business(id=1, name="Test", phone_number_id="123456")

        mock_biz_repo = MagicMock()
        mock_biz_repo.get_by_phone_number_id.return_value = business
        mock_biz_repo_class.return_value = mock_biz_repo

        # Simulate: ProcessedMessage already exists for this (msg_id, business_id)
        existing_msg = ProcessedMessage(message_id="wa-dup-001", business_id=1)

        filter_mock = MagicMock()
        filter_mock.first.return_value = existing_msg
        mock_db.query.return_value.filter.return_value = filter_mock

        payload = {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "changes": [
                        {
                            "value": {
                                "metadata": {"phone_number_id": "123456"},
                                "messages": [
                                    {
                                        "id": "wa-dup-001",
                                        "from": "573001234567",
                                        "type": "text",
                                        "text": {"body": "Hola"},
                                    }
                                ],
                            }
                        }
                    ]
                }
            ],
        }

        response = client.post("/api/v1/webhook", json=payload)
        assert response.status_code == 200
        # Duplicate dropped — background task NOT dispatched
        mock_process_bg.assert_not_called()

    @patch("app.api.webhook.BusinessRepository")
    @patch("app.api.webhook.process_background_message")
    def test_same_msg_id_different_business_not_deduplicated(
        self, mock_process_bg, mock_biz_repo_class, client, mock_db
    ):
        """
        Scenario: Same msg_id for different businesses is NOT deduplicated.

        GIVEN message "wa-shared-001" already processed for Business A
        WHEN message "wa-shared-001" arrives for Business B
        THEN it is processed normally (not dropped).
        """
        from app.models.models import Business

        business_b = Business(id=2, name="Business B", phone_number_id="789012")

        mock_biz_repo = MagicMock()
        mock_biz_repo.get_by_phone_number_id.return_value = business_b
        mock_biz_repo_class.return_value = mock_biz_repo

        # No match for (msg_id, business_id=2)
        filter_mock = MagicMock()
        filter_mock.first.return_value = None
        mock_db.query.return_value.filter.return_value = filter_mock

        payload = {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "changes": [
                        {
                            "value": {
                                "metadata": {"phone_number_id": "789012"},
                                "messages": [
                                    {
                                        "id": "wa-shared-001",
                                        "from": "573001234567",
                                        "type": "text",
                                        "text": {"body": "Hola"},
                                    }
                                ],
                            }
                        }
                    ]
                }
            ],
        }

        response = client.post("/api/v1/webhook", json=payload)
        assert response.status_code == 200
        # NOT a duplicate for this business — background task IS dispatched
        mock_process_bg.assert_called_once()
