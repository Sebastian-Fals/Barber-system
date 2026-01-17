import datetime
import json
import os
import sys
from unittest.mock import MagicMock, patch

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import SessionLocal
from app.models.models import Appointment, Barber, Business, Customer, CustomerData
from app.repositories.barber_repository import BarberRepository
from app.repositories.business_repository import BusinessRepository
from app.repositories.customer_repository import CustomerRepository
from app.services.handlers.booking_handler import BookingHandler

# Mock WhatsApp
sys.modules["app.services.whatsapp_service"] = MagicMock()


def verify_booking_handler():
    print("--- Verifying BookingHandler ---")
    db = SessionLocal()
    try:
        # Setup Data
        cust_repo = CustomerRepository(db)
        biz_repo = BusinessRepository(db)
        barber_repo = BarberRepository(db)

        # Create entities
        biz = biz_repo.create({"name": "TestBiz", "phone_number_id": "888"})
        barber = barber_repo.create({"name": "BarberTest", "business_id": biz.id, "phone": "111"})
        cust = cust_repo.create({"phone": "573008888888", "name": "Tester Booking"})

        # Init Handler
        handler = BookingHandler(db, "888")

        with patch("app.services.handlers.booking_handler.whatsapp_service") as mock_whatsapp:
            # 1. Select Barber
            print("\n[1] Testing interact: Barber Selection...")
            # Simulate User clicking "barber_{id}" (Usually triggered from Welcome menu)
            interactive_id = f"barber_{barber.id}"
            handler.handle_interactive(cust, interactive_id, {})

            db.refresh(cust)
            assert cust.conversation_state == CustomerData.SELECT_DATE
            data = json.loads(cust.conversation_data)
            assert data["barber_id"] == barber.id
            mock_whatsapp.send_interactive_button.assert_called()
            print("    -> State: SELECT_DATE | Data: barber_id saved | Msg Sent: OK")

            # 2. Select Date (Tomorrow)
            print("\n[2] Testing interact: Date Selection...")
            # Mock get_available_slots to return dummy slots
            # We patch the instance method on the handler's booking_service
            dummy_slots = [
                datetime.datetime(2023, 1, 1, 10, 0),
                datetime.datetime(2023, 1, 1, 11, 0),
                datetime.datetime(2023, 1, 1, 12, 0),
            ]
            with patch.object(handler.booking_service, "get_available_slots", return_value=dummy_slots):
                handler.handle_interactive(cust, "date_tomorrow", {})

            db.refresh(cust)
            assert cust.conversation_state == CustomerData.SELECT_SLOT
            data = json.loads(cust.conversation_data)
            assert "date" in data
            print("    -> State: SELECT_SLOT | Data: date saved | Slots Sent: OK")

            # 3. Select Time
            print("\n[3] Testing interact: Time Selection...")
            time_str = "10:00"
            handler.handle_interactive(cust, f"time_{time_str}", {})

            db.refresh(cust)
            assert cust.conversation_state == CustomerData.CONFIRM_BOOKING
            data = json.loads(cust.conversation_data)
            assert data["time"] == time_str
            print("    -> State: CONFIRM_BOOKING | Data: time saved | Summary Sent: OK")

            # 4. Confirm
            print("\n[4] Testing interact: Confirm...")
            # Mock create_appointment
            mock_appt = Appointment(id=123)
            with patch.object(handler.booking_service, "create_appointment", return_value=mock_appt):
                handler.handle_interactive(cust, "confirm_yes", {})

            db.refresh(cust)
            assert cust.conversation_state == CustomerData.IDLE
            print("    -> State: IDLE | Appt Created | Confimed Msg Sent: OK")

        # Cleanup
        db.delete(cust)
        db.delete(barber)
        db.delete(biz)
        db.commit()
        print("\n--- BookingHandler Verification PASSED ---")

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
    verify_booking_handler()
