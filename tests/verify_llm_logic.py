import datetime
import os
import sys
from unittest.mock import MagicMock, patch

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.models.models import Business, Customer  # noqa: E402
from app.services.handlers.query_handler import QueryHandler  # noqa: E402


def test_booking_intent():
    print("\n--- Testing 'Quiero una cita' Intent ---")

    # 1. Mock Dependencies
    mock_db = MagicMock()
    mock_customer = Customer(
        id=1,
        name="TestUser",
        phone="573001234567",
        phone_hash="hash",
        conversation_state="IDLE",
        conversation_data="{}",
    )
    mock_business = Business(id=1, name="BarberShop", phone_number_id="123", phone="555")

    # Mock Repos
    mock_customer_repo = MagicMock()
    mock_barber_repo = MagicMock()
    mock_business_repo = MagicMock()
    mock_appt_repo = MagicMock()
    mock_booking_service = MagicMock()

    # Mock LLM Service Response
    mock_llm_response = {
        "intent": "BOOK_APPOINTMENT",
        "extracted": {"barber_name": "Juan", "date": "2026-02-01", "time": "15:00"},
        "reply": "Claro, busquemos cita con Juan.",
    }

    with patch(
        "app.services.handlers.query_handler.llm_service.analyze_message", return_value=mock_llm_response
    ) as mock_analyze:
        with patch("app.services.handlers.query_handler.whatsapp_service"):
            # Init Handler with mocks
            handler = QueryHandler(mock_db, "123")
            handler.customer_repo = mock_customer_repo
            handler.barber_repo = mock_barber_repo
            handler.business_repo = mock_business_repo
            handler.appt_repo = mock_appt_repo
            handler.booking_service = mock_booking_service
            handler.business = mock_business

            # Setup specific mock returns
            mock_barber = MagicMock()
            mock_barber.id = 10
            mock_barber.name = "Juan Barber"
            mock_barber_repo.get_by_business.return_value = [mock_barber]

            # Run
            handler.handle_message(mock_customer, "Quiero cita con Juan para el 1 de febrero a las 3pm")

            # Assertions
            print(f"LLM Called: {mock_analyze.called}")
            print(f"Extracted Date applied to State: {mock_customer_repo.update_state.called}")

            # Verify update_data was called with correct structure
            args, _ = mock_customer_repo.update_data.call_args
            print(f"Data Update: {args[1]}")

            if '"barber_id": 10' in args[1] and '"date": "2026-02-01"' in args[1]:
                print("✅ PASS: Booking Intent Correctly Parsed & State Updated")
            else:
                print("❌ FAIL: Data not updated correctly")


def test_cancellation_direct_intent():
    print("\n--- Testing 'Cancelar cita' Intent ---")

    mock_db = MagicMock()
    # User has an active appointment
    mock_customer = Customer(id=1, name="TestUser", phone="573001234567")
    mock_appt = MagicMock()
    mock_appt.id = 999
    # Simulate DB time (UTC) matching the requested "tomorrow" logic, but simplified matching here
    mock_appt.start_time = datetime.datetime.now(datetime.timezone.utc)
    mock_appt.barber.name = "Juan"

    # Mock LLM
    mock_llm_response = {"intent": "CANCEL_APPOINTMENT", "extracted": {"date": "2026-02-01"}, "reply": "Revisando..."}

    with patch("app.services.handlers.query_handler.llm_service.analyze_message", return_value=mock_llm_response):
        with patch("app.services.handlers.query_handler.whatsapp_service"):
            handler = QueryHandler(mock_db, "123")
            handler.appt_repo = MagicMock()
            handler.appt_repo.get_active_for_customer.return_value = [mock_appt]
            handler.booking_service = MagicMock()
            handler.booking_service.cancel_appointment.return_value = True

            # Patch the source since it is imported inside the function
            with patch("app.core.datetime_utils.to_local") as mock_to_local:
                mock_dt = datetime.datetime(2026, 2, 1, 10, 0)
                mock_to_local.return_value = mock_dt

                handler.handle_message(mock_customer, "Cancelar mi cita del 1 de feb")

                if handler.booking_service.cancel_appointment.called:
                    print("✅ PASS: Cancellation service called for identified appointment")
                else:
                    print("❌ FAIL: Cancellation service NOT called")


if __name__ == "__main__":
    test_booking_intent()
    test_cancellation_direct_intent()
