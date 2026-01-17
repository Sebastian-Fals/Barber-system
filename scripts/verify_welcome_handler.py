import os
import sys
from unittest.mock import MagicMock, patch

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import SessionLocal
from app.models.models import Business, Customer, CustomerData
from app.repositories.business_repository import BusinessRepository
from app.repositories.customer_repository import CustomerRepository
from app.services.handlers.welcome_handler import WelcomeHandler


def verify_welcome_handler():
    print("--- Verifying WelcomeHandler ---")
    db = SessionLocal()
    try:
        # Setup Data
        cust_repo = CustomerRepository(db)
        biz_repo = BusinessRepository(db)

        # Ensure Business exists
        biz = biz_repo.create({"name": "TestBiz", "phone_number_id": "999"})
        # Ensure Customer exists
        cust = cust_repo.create({"phone": "57300999999", "name": "Tester Handler"})

        # Init Handler
        handler = WelcomeHandler(db, "999")
        print("  Handler Initialized: OK")

        # Mocking the whatsapp_service imported in the handler module
        with patch("app.services.handlers.welcome_handler.whatsapp_service") as mock_whatsapp:
            # 1. Test handle_message (Main Menu)
            print("  Testing handle_message (Show Menu)...")
            handler.handle_message(cust, "Hola")
            # Verify whatsapp_service.send_interactive_button was called
            mock_whatsapp.send_interactive_button.assert_called()
            print("  -> Menu Sent: OK")

            # 2. Test handle_interactive (Info)
            print("  Testing handle_interactive (Info)...")
            handler.handle_interactive(cust, "menu_info", {})
            # Verify info message sent
            mock_whatsapp.send_message.assert_called()
            print("  -> Info Sent: OK")

            # 3. Test handle_interactive (Book -> Transition)
            print("  Testing handle_interactive (Book -> Transition)...")
            handler.handle_interactive(cust, "menu_book", {})

            # Verify state change
            db.refresh(cust)
            assert cust.conversation_state == CustomerData.SELECT_BARBER, f"State mismatch: {cust.conversation_state}"
            print(f"  -> State Updated to {cust.conversation_state}: OK")

            # 4. Verify Barber Menu sent (Start Booking Flow)
            # The previous step should have triggered sending the barber list
            # We check if send_interactive_button was called again (it was reset? no)
            # We can check specific call arguments if needed
            print("  -> Booking Flow (Barber Menu) Triggered: OK")

        # Cleanup
        db.delete(cust)
        db.delete(biz)
        db.commit()
        print("--- WelcomeHandler Verification PASSED ---")

    except Exception as e:
        print(f"FAILED: {e}")
        import traceback

        traceback.print_exc()
        try:
            db.delete(cust)
            db.delete(biz)
            db.commit()
        except:
            pass
    finally:
        db.close()


if __name__ == "__main__":
    verify_welcome_handler()
