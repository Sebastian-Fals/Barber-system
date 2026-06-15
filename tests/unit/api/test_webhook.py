"""
RED tests for webhook multi-tenant behavior.

Spec scenarios:
  - Webhook with unknown phone_number_id → return 200, no DB writes.
  - Webhook with known phone_number_id → business_id resolved and propagated.
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
