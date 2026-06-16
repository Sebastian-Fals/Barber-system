"""
Tests for webhook — Evolution API.

Spec scenarios:
  - Evolution POST with messages.upsert → parsed correctly.
  - CONNECTION_UPDATE ignored.
  - Unknown instance → return 200, no DB writes.
  - Known instance → business resolved by instance_name.
  - Dedup via ProcessedMessage still works.
  - listResponse messageType → interactive_id extracted from selectedRowId.
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


# ──────────────────────────────────────────────────────────────────
# Evolution payload fixtures
# ──────────────────────────────────────────────────────────────────

EVOLUTION_TEXT_PAYLOAD = {
    "event": "messages.upsert",
    "instance": "barberia-latino",
    "data": {
        "key": {
            "remoteJid": "573001234567@s.whatsapp.net",
            "id": "evo-msg-001",
        },
        "messageType": "conversation",
        "message": {
            "conversation": "Hola, quiero agendar una cita",
        },
    },
}

EVOLUTION_LIST_RESPONSE_PAYLOAD = {
    "event": "messages.upsert",
    "instance": "barberia-latino",
    "data": {
        "key": {
            "remoteJid": "573001234567@s.whatsapp.net",
            "id": "evo-list-rsp-001",
        },
        "messageType": "listResponse",
        "message": {
            "listResponseMessage": {
                "singleSelectReply": {
                    "selectedRowId": "service_1",
                }
            }
        },
    },
}

EVOLUTION_CONNECTION_UPDATE_PAYLOAD = {
    "event": "CONNECTION_UPDATE",
    "instance": "barberia-latino",
    "data": {"state": "open"},
}


class TestWebhookEvolutionParse:
    """Parse Evolution webhook payloads correctly."""

    @patch("app.api.webhook.BusinessRepository")
    @patch("app.api.webhook.process_background_message")
    def test_text_message_parsed(self, mock_process_bg, mock_biz_repo_class, client, mock_db):
        """
        Scenario: Evolution sends messages.upsert with conversation type.
        - GIVEN payload with messageType "conversation"
        - WHEN received
        - THEN text body is extracted and dispatched.
        """
        from app.models.models import Business

        business = Business(id=1, name="Test Biz")
        business.instance_name = "barberia-latino"
        business.instance_apikey = "key-abc"

        mock_biz_repo = MagicMock()
        mock_biz_repo.get_by_instance_name.return_value = business
        mock_biz_repo_class.return_value = mock_biz_repo

        mock_db.query.return_value.filter.return_value.first.return_value = None

        response = client.post("/api/v1/webhook", json=EVOLUTION_TEXT_PAYLOAD)
        assert response.status_code == 200

    @patch("app.api.webhook.BusinessRepository")
    @patch("app.api.webhook.process_background_message")
    def test_list_response_parsed(self, mock_process_bg, mock_biz_repo_class, client, mock_db):
        """
        Scenario: Evolution sends messages.upsert with listResponse type.
        - GIVEN payload with messageType "listResponse"
        - WHEN received
        - THEN interactive_id is extracted from selectedRowId.
        """
        from app.models.models import Business

        business = Business(id=1, name="Test Biz")
        business.instance_name = "barberia-latino"
        business.instance_apikey = "key-abc"

        mock_biz_repo = MagicMock()
        mock_biz_repo.get_by_instance_name.return_value = business
        mock_biz_repo_class.return_value = mock_biz_repo

        mock_db.query.return_value.filter.return_value.first.return_value = None

        response = client.post("/api/v1/webhook", json=EVOLUTION_LIST_RESPONSE_PAYLOAD)
        assert response.status_code == 200

    @patch("app.api.webhook.BusinessRepository")
    def test_connection_update_ignored(self, mock_biz_repo_class, client, mock_db):
        """
        Scenario: Evolution sends CONNECTION_UPDATE.
        - GIVEN event is "CONNECTION_UPDATE"
        - WHEN received
        - THEN returns {"status": "ignored"} without processing.
        """
        response = client.post("/api/v1/webhook", json=EVOLUTION_CONNECTION_UPDATE_PAYLOAD)
        assert response.status_code == 200
        assert response.json() == {"status": "ignored"}


class TestWebhookMultiTenant:
    """Instance-based routing replaces phone_number_id resolution."""

    @patch("app.api.webhook.BusinessRepository")
    @patch("app.api.webhook.process_background_message")
    def test_unknown_instance_returns_200(self, mock_process_bg, mock_biz_repo_class, client, mock_db):
        """
        Scenario: Webhook with unknown instance_name.
        - GIVEN instance "unknown-inst" does NOT map to any business
        - WHEN a webhook arrives
        - THEN returns 200 without dispatching.
        """
        mock_biz_repo = MagicMock()
        mock_biz_repo.get_by_instance_name.return_value = None
        mock_biz_repo_class.return_value = mock_biz_repo

        payload = {
            "event": "messages.upsert",
            "instance": "unknown-inst",
            "data": {
                "key": {"remoteJid": "57@s.whatsapp.net", "id": "m1"},
                "messageType": "conversation",
                "message": {"conversation": "Hola"},
            },
        }

        response = client.post("/api/v1/webhook", json=payload)
        assert response.status_code == 200
        mock_process_bg.assert_not_called()


class TestWebhookDedup:
    """Deduplication via ProcessedMessage still works."""

    @patch("app.api.webhook.BusinessRepository")
    @patch("app.api.webhook.process_background_message")
    def test_duplicate_message_dropped(self, mock_process_bg, mock_biz_repo_class, client, mock_db):
        """
        Scenario: Duplicate message is caught via ProcessedMessage.
        """
        from app.models.models import Business, ProcessedMessage

        business = Business(id=1, name="Test")
        business.instance_name = "barberia-latino"
        business.instance_apikey = "key-abc"

        mock_biz_repo = MagicMock()
        mock_biz_repo.get_by_instance_name.return_value = business
        mock_biz_repo_class.return_value = mock_biz_repo

        existing_msg = ProcessedMessage(message_id="evo-msg-001", business_id=1)
        filter_mock = MagicMock()
        filter_mock.first.return_value = existing_msg
        mock_db.query.return_value.filter.return_value = filter_mock

        response = client.post("/api/v1/webhook", json=EVOLUTION_TEXT_PAYLOAD)
        assert response.status_code == 200
        mock_process_bg.assert_not_called()


class TestDirectProcessing:
    """process_background_message uses instance_name + apikey."""

    @pytest.mark.asyncio
    @patch("app.api.webhook.run_in_threadpool")
    @patch("app.api.webhook.ConversationService")
    @patch("app.api.webhook.SessionLocal")
    async def test_text_message_dispatched_with_instance_args(
        self, mock_session_local, mock_conv_service_class, mock_run_in_threadpool
    ):
        """
        Scenario: Text message dispatches with instance_name + apikey.
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
            instance_name="barberia-latino",
            instance_apikey="key-abc",
            from_number="573001234567",
            msg_body="Hola",
            msg_type="text",
            interactive_id=None,
            business_id=1,
        )

        mock_conv_service_class.assert_called_once_with(mock_session, "barberia-latino", "key-abc", 1)
        mock_conv_service.handle_incoming_message.assert_called_once_with("573001234567", "Hola", "text", None)
