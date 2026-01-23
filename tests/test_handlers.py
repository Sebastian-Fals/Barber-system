from unittest.mock import MagicMock, patch

from app.models.models import Customer
from app.services.handlers.welcome_handler import WelcomeHandler


@patch("app.services.handlers.welcome_handler.message_loader")
@patch("app.services.handlers.welcome_handler.whatsapp_service")
def test_welcome_output(mock_ws, mock_loader):
    db_session = MagicMock()
    # Setup
    mock_loader.get.return_value = "Hola"
    # Setup
    mock_business = MagicMock()
    mock_business.id = 1
    mock_business.name = "Test Biz"

    # Mock DB Query
    db_session.query.return_value.filter.return_value.first.return_value = mock_business

    # Init Handler
    handler = WelcomeHandler(db_session, "123")

    # Mock Customer
    customer = Customer(id=1, phone="555", name="Joe")

    # Run
    handler.handle_message(customer, "Hola")

    # Verify
    mock_ws.send_interactive_button.assert_called()
    print("✅ Welcome Handler Passed")
