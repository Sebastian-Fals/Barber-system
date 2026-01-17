import os
import sys
from unittest.mock import MagicMock, patch

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import SessionLocal
from app.models.models import Appointment, Business, Customer, CustomerData
from app.repositories.appointment_repository import AppointmentRepository
from app.repositories.barber_repository import BarberRepository
from app.repositories.business_repository import BusinessRepository
from app.repositories.customer_repository import CustomerRepository
from app.services.handlers.query_handler import QueryHandler

# Mock Services
sys.modules["app.services.whatsapp_service"] = MagicMock()
sys.modules["app.services.llm_service"] = MagicMock()


def verify_query_handler():
    print("--- Verifying QueryHandler ---")
    db = SessionLocal()
    try:
        # Setup Data
        cust_repo = CustomerRepository(db)
        biz_repo = BusinessRepository(db)
        barber_repo = BarberRepository(db)
        appt_repo = AppointmentRepository(db)

        # Create entities
        biz = biz_repo.create({"name": "TestBiz", "phone_number_id": "777"})
        barber = barber_repo.create({"name": "BarberGenius", "business_id": biz.id, "phone": "222"})
        cust = cust_repo.create({"phone": "573007777777", "name": "Tester Query"})

        # Init Handler
        handler = QueryHandler(db, "777")

        with patch("app.services.handlers.query_handler.whatsapp_service") as mock_whatsapp, patch(
            "app.services.handlers.query_handler.llm_service"
        ) as mock_llm:
            # 1. Test QNA Intent
            print("\n[1] Testing QNA Intent...")
            mock_llm.analyze_message.return_value = {"intent": "INFO", "reply": "Simulated AI Reply"}

            handler.handle_message(cust, "Info about hours")

            mock_llm.analyze_message.assert_called()
            mock_whatsapp.send_message.assert_called_with("777", cust.phone, "Simulated AI Reply")
            print("    -> LLM Called | Reply Sent: OK")

            # 2. Test BOOKING Intent
            print("\n[2] Testing BOOKING Intent...")
            mock_llm.analyze_message.return_value = {"intent": "BOOKING", "reply": "Claro, agendemos."}

            handler.handle_message(cust, "I want to book")

            db.refresh(cust)
            assert cust.conversation_state == CustomerData.SELECT_BARBER
            # Check if interactive buttons (barber list) were sent
            mock_whatsapp.send_interactive_button.assert_called()
            print("    -> State: SELECT_BARBER | Barber/Menu Sent: OK")

            # 3. Test CANCEL Intent
            print("\n[3] Testing CANCEL Intent...")
            # Create dummy appointment to cancel
            # We mock get_active_for_customer
            mock_appt = Appointment(
                id=999, barber_id=barber.id, start_time=None
            )  # Start time/end time irrelevant for mock object if not accessing
            # Actually we need to mock db query or create real appointment.
            # Real appt creation is safer for integration test?
            # Let's mock the repo/service calls on the handler to be unit-test style.

            with patch.object(handler.appt_repo, "get_active_for_customer", return_value=[mock_appt]), patch.object(
                handler.booking_service, "cancel_appointment", return_value=True
            ) as mock_cancel:
                mock_llm.analyze_message.return_value = {"intent": "CANCEL", "reply": "Canceling..."}

                handler.handle_message(cust, "Cancel my appointment")

                mock_cancel.assert_called_with(999)
                mock_whatsapp.send_message.assert_called()  # Success message
                print("    -> Cancel called on Appt 999 | Success Msg Sent: OK")

        # Cleanup
        db.delete(cust)
        db.delete(barber)
        db.delete(biz)
        db.commit()
        print("\n--- QueryHandler Verification PASSED ---")

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
    verify_query_handler()
