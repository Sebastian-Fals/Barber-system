import os
import sys

sys.path.append(os.getcwd())

from unittest.mock import MagicMock, patch  # noqa: E402

try:
    print("Importing ConversationService...")
    from app.features.communication.conversation_service import ConversationService
    from app.models.models import Customer, CustomerData

    print("Imported.")

    # Mock DB
    db = MagicMock()
    # Mock Handlers at class level to avoid init
    with patch("app.features.communication.conversation_service.QueryHandler"), patch(
        "app.features.communication.conversation_service.BookingHandler"
    ), patch("app.features.communication.conversation_service.WelcomeHandler"), patch(
        "app.features.communication.whatsapp_service.whatsapp_service"
    ) as mock_ws:
        service = ConversationService(db, "123")
        service.customer_repo = MagicMock()
        service.business_repo = MagicMock()

        print("Testing 'Hola' rejection...")
        customer = Customer(id=1, phone="555", name="Usuario", conversation_state=CustomerData.WAITING_NAME)
        service._route_text_message(customer, "Hola")

        if mock_ws.send_message.called:
            print("✅ PASS: 'Hola' triggered invalid name warning.")
        else:
            print("❌ FAIL: 'Hola' was accepted (should be rejected).")

        print("Testing 'Sebastian' acceptance...")
        mock_ws.reset_mock()
        customer2 = Customer(id=2, phone="555", conversation_state=CustomerData.WAITING_NAME)
        service._route_text_message(customer2, "Sebastian")

        if service.customer_repo.update.called:
            print("✅ PASS: 'Sebastian' triggered update.")
        else:
            print("❌ FAIL: 'Sebastian' NOT updated.")

except Exception:
    import traceback

    traceback.print_exc()
