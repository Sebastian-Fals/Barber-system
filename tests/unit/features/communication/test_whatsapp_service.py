"""
Tests for WhatsAppService — Evolution API.

Spec: send_message → POST /message/sendText/{instance} with apikey header,
      send_list → POST /message/sendList/{instance} with correct body shape.
"""

from unittest.mock import MagicMock, patch

from app.features.communication.whatsapp_service import WhatsAppService


class TestWhatsAppServiceSendMessage:
    """send_message POSTs to Evolution /message/sendText/{instance}."""

    @patch("app.features.communication.whatsapp_service.requests")
    def test_send_message_posts_to_correct_url(self, mock_requests):
        """send_message must POST to /message/sendText/{instance_name}."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "ok"}
        mock_requests.post.return_value = mock_response

        service = WhatsAppService()
        result = service.send_message(
            instance_name="barberia-latino",
            apikey="abc123",
            to="573001234567",
            body="Hola, bienvenido!",
        )

        assert result is not None
        mock_requests.post.assert_called_once()
        url = mock_requests.post.call_args[0][0]
        assert "/message/sendText/barberia-latino" in url

    @patch("app.features.communication.whatsapp_service.requests")
    def test_send_message_sends_apikey_header(self, mock_requests):
        """send_message must include apikey header."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "ok"}
        mock_requests.post.return_value = mock_response

        service = WhatsAppService()
        service.send_message(
            instance_name="chapinero",
            apikey="def456",
            to="573002345678",
            body="Test message",
        )

        headers = mock_requests.post.call_args[1].get("headers", {})
        assert headers.get("apikey") == "def456", f"Expected apikey='def456', got headers={headers}"

    @patch("app.features.communication.whatsapp_service.requests")
    def test_send_message_body_contains_number_and_text(self, mock_requests):
        """send_message body must have 'number' and 'text' fields."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_requests.post.return_value = mock_response

        service = WhatsAppService()
        service.send_message(
            instance_name="test-inst",
            apikey="key123",
            to="573001234567",
            body="Hola mundo",
        )

        body = mock_requests.post.call_args[1].get("json", {})
        assert body.get("number") == "573001234567"
        assert body.get("text") == "Hola mundo"

    @patch("app.features.communication.whatsapp_service.requests")
    def test_send_message_returns_none_on_request_exception(self, mock_requests):
        """send_message returns None when request fails."""
        mock_requests.exceptions = __import__("requests").exceptions
        mock_requests.post.side_effect = __import__("requests").exceptions.RequestException("Timeout")

        service = WhatsAppService()
        result = service.send_message(
            instance_name="inst",
            apikey="k",
            to="57300",
            body="msg",
        )

        assert result is None


class TestWhatsAppServiceSendList:
    """send_list POSTs to Evolution /message/sendList/{instance}."""

    @patch("app.features.communication.whatsapp_service.requests")
    def test_send_list_posts_to_correct_url(self, mock_requests):
        """send_list must POST to /message/sendList/{instance_name}."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_requests.post.return_value = mock_response

        service = WhatsAppService()
        rows = [
            {"title": "Corte Clasico", "description": "30 min", "rowId": "service_1"},
            {"title": "Barba", "description": "20 min", "rowId": "service_2"},
        ]
        service.send_list(
            instance_name="barberia-latino",
            apikey="abc123",
            to="573001234567",
            title="Nuestros Servicios",
            description="Elige una opcion",
            button_text="Ver",
            footer_text="Barberia Sebastian",
            rows=rows,
        )

        assert mock_requests.post.called
        url = mock_requests.post.call_args[0][0]
        assert "/message/sendList/barberia-latino" in url

    @patch("app.features.communication.whatsapp_service.requests")
    def test_send_list_body_has_correct_shape(self, mock_requests):
        """send_list body must include title, description, buttonText, footerText, sections."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_requests.post.return_value = mock_response

        service = WhatsAppService()
        rows = [{"title": "Opcion 1", "description": "Desc 1", "rowId": "opt_1"}]
        service.send_list(
            instance_name="inst",
            apikey="key",
            to="57300",
            title="Menu",
            description="Elige",
            button_text="Abrir",
            footer_text="Footer",
            rows=rows,
        )

        body = mock_requests.post.call_args[1].get("json", {})
        assert body.get("number") == "57300"
        assert body.get("title") == "Menu"
        assert body.get("description") == "Elige"
        assert body.get("buttonText") == "Abrir"
        assert body.get("footerText") == "Footer"
        assert "sections" in body
        assert len(body["sections"]) == 1
        section = body["sections"][0]
        assert "rows" in section
        assert len(section["rows"]) == 1
        assert section["rows"][0]["rowId"] == "opt_1"

    @patch("app.features.communication.whatsapp_service.requests")
    def test_send_list_sends_apikey_header(self, mock_requests):
        """send_list must include apikey header."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_requests.post.return_value = mock_response

        service = WhatsAppService()
        service.send_list(
            instance_name="test",
            apikey="my-key",
            to="57300",
            title="T",
            description="D",
            button_text="B",
            footer_text="F",
            rows=[],
        )

        headers = mock_requests.post.call_args[1].get("headers", {})
        assert headers.get("apikey") == "my-key"

    @patch("app.features.communication.whatsapp_service.requests")
    def test_send_list_returns_none_on_error(self, mock_requests):
        """send_list returns None on request exception."""
        mock_requests.exceptions = __import__("requests").exceptions
        mock_requests.post.side_effect = __import__("requests").exceptions.RequestException("Error")

        service = WhatsAppService()
        result = service.send_list(
            instance_name="x",
            apikey="y",
            to="z",
            title="T",
            description="D",
            button_text="B",
            footer_text="F",
            rows=[],
        )
        assert result is None
