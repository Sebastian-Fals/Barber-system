import unittest
from unittest.mock import MagicMock, patch

from app.features.communication.conversation_service import ConversationService
from app.models.models import Customer, CustomerData


class TestNameValidation(unittest.TestCase):
    @patch("app.features.communication.conversation_service.QueryHandler")
    @patch("app.features.communication.conversation_service.BookingHandler")
    @patch("app.features.communication.conversation_service.WelcomeHandler")
    @patch("app.features.communication.conversation_service.whatsapp_service")
    def test_invalid_name_rejected(self, mock_ws, mock_welcome, mock_booking, mock_query):
        # Setup
        db = MagicMock()
        service = ConversationService(db, "123", 1)

        # Mock Customer in WAITING_NAME state (using new mock structure)
        customer = Customer(
            id=1, phone="555", name="Usuario", conversation_state=CustomerData.WAITING_NAME, business_id=1
        )

        # Mock Repo injection (ConversationService creates them, but we can override or mock constructors too)
        # Actually easier to override after init or mock constructors.
        # But we want to test _route_text_message.

        service.customer_repo = MagicMock()
        service.business_repo = MagicMock()
        # Handlers are already mocked by class patches (service.welcome_handler is a Mock instance)

        # Action: User says "Hola"
        service._route_text_message(customer, "Hola")

        # Verify
        service.customer_repo.update.assert_not_called()
        mock_ws.send_message.assert_called()
        args = mock_ws.send_message.call_args[0]
        assert "ese no parece un nombre" in args[2]
        print("✅ 'Hola' rejected correctly")

    @patch("app.features.communication.conversation_service.QueryHandler")
    @patch("app.features.communication.conversation_service.BookingHandler")
    @patch("app.features.communication.conversation_service.WelcomeHandler")
    @patch("app.features.communication.conversation_service.whatsapp_service")
    def test_valid_name_accepted(self, mock_ws, mock_welcome, mock_booking, mock_query):
        # Setup
        db = MagicMock()
        service = ConversationService(db, "123", 1)

        customer = Customer(id=1, phone="555", conversation_state=CustomerData.WAITING_NAME, business_id=1)
        service.customer_repo = MagicMock()
        service.business_repo = MagicMock()

        # Action: User says "Sebastian"
        service._route_text_message(customer, "Sebastian")

        # Verify
        service.customer_repo.update.assert_called_with(customer, {"name": "Sebastian"})
        assert service.customer_repo.update_state.called
        print("✅ 'Sebastian' accepted")

        # Action: User says "Sebastian"
        service._route_text_message(customer, "Sebastian")

        # Verify: Name Updated to Title Case
        service.customer_repo.update.assert_called_with(customer, {"name": "Sebastian"})
        assert service.customer_repo.update_state.called  # Should set to IDLE
        print("✅ 'Sebastian' accepted")


if __name__ == "__main__":
    unittest.main()
