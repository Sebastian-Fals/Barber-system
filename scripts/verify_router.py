import os
import sys
from unittest.mock import MagicMock, patch

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import SessionLocal
from app.models.models import Barber, Business, Customer, CustomerData
from app.repositories.barber_repository import BarberRepository
from app.repositories.business_repository import BusinessRepository
from app.repositories.customer_repository import CustomerRepository
from app.services.conversation_service import ConversationService

# We need to ensure LLM is mocked inside QueryHandler or globally
sys.modules["app.services.llm_service"] = MagicMock()


def verify_router_flow():
    print("--- Verifying ConversationRouter Flow ---")
    db = SessionLocal()
    try:
        # Setup Data
        cust_repo = CustomerRepository(db)
        biz_repo = BusinessRepository(db)
        barber_repo = BarberRepository(db)

        # Entities
        # Use existing or create new.
        # Clean previous test user if exists
        old_cust = cust_repo.get_by_phone("573005555555")
        if old_cust:
            db.delete(old_cust)
            db.commit()

        biz = biz_repo.create({"name": "RouterBiz", "phone_number_id": "555"})
        barber = barber_repo.create({"name": "RouterBarber", "business_id": biz.id, "phone": "333"})

        # Patching the logical service instances used by handlers
        # Assuming handlers import 'whatsapp_service' from 'app.services.whatsapp_service'
        # We patch the instance in that module.
        with patch("app.services.whatsapp_service.whatsapp_service") as mock_wa, patch(
            "app.services.llm_service.llm_service"
        ) as mock_llm:
            # Init Service with active mocks
            service = ConversationService(db, "555")

            # 1. New User Says "Hola"
            print("\n[1] Flow: New User 'Hola'...")
            service.handle_incoming_message("573005555555", "Hola", "text")

            # Check Customer Created
            cust = cust_repo.get_by_phone("573005555555")
            assert cust is not None, "Customer should be created"
            # Check Welcome Handler called (Menu Sent)
            mock_wa.send_interactive_button.assert_called()
            print("    -> Customer Created | Welcome Menu Sent: OK")

            # 2. User clicks "menu_book"
            print("\n[2] Flow: User clicks 'menu_book'...")
            service.handle_incoming_message("573005555555", "", "interactive", "menu_book")

            db.refresh(cust)
            assert cust.conversation_state == CustomerData.SELECT_BARBER
            # Check Welcome/Booking flow triggered (Barber list sent)
            assert mock_wa.send_interactive_button.call_count >= 2
            print("    -> State: SELECT_BARBER | Barber List Sent: OK")

            # 3. User clicks "barber_{id}"
            print("\n[3] Flow: User Selects Barber...")
            service.handle_incoming_message("573005555555", "", "interactive", f"barber_{barber.id}")

            db.refresh(cust)
            assert cust.conversation_state == CustomerData.SELECT_DATE
            # Booking Handler should have sent Date Prompt
            mock_wa.send_interactive_button.assert_called()
            print("    -> State: SELECT_DATE | Date Prompt Sent: OK")

            # 4. User types "cancelar"
            print("\n[4] Flow: Global 'cancelar' command...")

            # Mock LLM Cancel response
            mock_llm.analyze_message.return_value = {"intent": "CANCEL", "reply": "Canceling..."}

            service.handle_incoming_message("573005555555", "cancelar", "text")

            # Query Handler should be called
            mock_llm.analyze_message.assert_called()
            mock_wa.send_message.assert_called()
            print("    -> Cancel intercepted | QueryHandler Triggered: OK")

        # Cleanup
        db.delete(cust)
        db.delete(barber)
        db.delete(biz)
        db.commit()
        print("\n--- Router Verification PASSED ---")

    except Exception as e:
        print(f"\n❌ FAILED: {e}")
        import traceback

        traceback.print_exc()
        try:
            db.delete(cust)
            db.delete(barber)
            db.delete(biz)
            db.commit()
        except:
            pass
    finally:
        db.close()


if __name__ == "__main__":
    verify_router_flow()
