"""
RED tests: Cancel flow in BookingHandler + cancel buttons in WelcomeHandler.

Spec: appointment-locking — Cancel text resets state.
"""
import json
from unittest.mock import MagicMock, patch

from app.models.models import Business, Customer, CustomerData
from app.services.handlers.booking_handler import BookingHandler
from app.services.handlers.welcome_handler import WelcomeHandler


class TestBookingHandlerCancel:
    """Tests for cancel text detection in BookingHandler."""

    def test_cancelar_text_during_booking_resets_to_idle(self):
        """
        Scenario: User types "cancelar" during booking flow.
        - GIVEN customer is in SELECT_BARBER state with conversation_data
        - WHEN they send the text "cancelar"
        - THEN state resets to IDLE and conversation_data is cleared.
        """
        db = MagicMock()
        business = Business(id=1, name="Test Biz")
        db.query.return_value.filter.return_value.first.return_value = business

        customer = Customer(
            id=1,
            phone="+57000123",
            name="Test",
            conversation_state=CustomerData.SELECT_BARBER,
            conversation_data=json.dumps({"barber_id": 1}),
        )

        handler = BookingHandler(db, "phone_id_123", business_id=1)

        with patch.object(handler, "_update_state") as mock_update:
            handler.handle_message(customer, "cancelar")

            # Verify _update_state was called with IDLE and empty data
            mock_update.assert_called_once()
            args, kwargs = mock_update.call_args
            assert args[0] == customer
            assert args[1] == CustomerData.IDLE
            assert args[2] == {}

    def test_cancelar_text_case_insensitive(self):
        """
        - GIVEN customer in SELECT_DATE state
        - WHEN they send "Cancelar" (mixed case)
        - THEN state resets to IDLE.
        """
        db = MagicMock()
        business = Business(id=1, name="Test Biz")
        db.query.return_value.filter.return_value.first.return_value = business

        customer = Customer(
            id=2,
            phone="+57000456",
            name="Test2",
            conversation_state=CustomerData.SELECT_DATE,
            conversation_data=json.dumps({"barber_id": 1, "date": "2026-06-20"}),
        )

        handler = BookingHandler(db, "phone_id_123", business_id=1)

        with patch.object(handler, "_update_state") as mock_update:
            handler.handle_message(customer, "Cancelar")

            mock_update.assert_called_once()
            args, _kwargs = mock_update.call_args
            assert args[1] == CustomerData.IDLE

    def test_non_cancel_text_not_handled_by_booking_handler(self):
        """
        - GIVEN customer sends random text (not "cancelar")
        - WHEN BookingHandler.handle_message processes it
        - THEN it returns False (not handled — falls through to LLM).
        """
        db = MagicMock()
        business = Business(id=1, name="Test Biz")
        db.query.return_value.filter.return_value.first.return_value = business

        customer = Customer(
            id=3,
            phone="+57000789",
            name="Test3",
            conversation_state=CustomerData.SELECT_BARBER,
        )

        handler = BookingHandler(db, "phone_id_123", business_id=1)
        result = handler.handle_message(customer, "quiero agendar")

        assert result is False, "Non-cancel text should not be handled by BookingHandler"


class TestWelcomeHandlerCancelButtons:
    """Tests for cancel buttons in 'Mis Citas' list."""

    @patch("app.services.handlers.welcome_handler.message_loader")
    @patch("app.services.handlers.welcome_handler.whatsapp_service")
    @patch("app.services.handlers.welcome_handler.AppointmentRepository")
    def test_show_my_appointments_includes_cancel_buttons(self, mock_repo_class, mock_ws, mock_loader):
        """
        - GIVEN customer has 1 confirmed appointment
        - WHEN _show_my_appointments is called
        - THEN an interactive message with cancel_appt_{id} button is sent.
        """
        from datetime import datetime, timezone

        from app.models.models import Appointment, AppointmentStatus, Barber

        db = MagicMock()
        business = Business(id=1, name="Test Biz")
        db.query.return_value.filter.return_value.first.return_value = business

        mock_barber = Barber(id=1, name="Carlos")
        mock_appt = Appointment(
            id=42,
            customer_id=1,
            barber_id=1,
            business_id=1,
            status=AppointmentStatus.CONFIRMED.value,
            start_time=datetime(2026, 6, 20, 10, 0, tzinfo=timezone.utc),
        )
        mock_appt.barber = mock_barber

        # Mock the appointment repository
        mock_repo = MagicMock()
        mock_repo.get_active_for_customer.return_value = [mock_appt]
        mock_repo_class.return_value = mock_repo

        mock_loader.get.return_value = "Tus Citas"

        handler = WelcomeHandler(db, "phone_id_123", business_id=1)
        customer = Customer(id=1, phone="+57000", name="Test")

        handler._show_my_appointments(customer)

        # Verify an interactive button message with cancel_appt_ is sent
        cancel_button_found = False
        for call in mock_ws.send_interactive_button.call_args_list:
            args, kwargs = call
            if len(args) >= 4:
                buttons = args[3]
            else:
                buttons = kwargs.get("buttons", [])
            for btn in buttons:
                if "cancel_appt_" in btn.get("id", ""):
                    cancel_button_found = True
                    break
            if cancel_button_found:
                break

        assert cancel_button_found, "Expected cancel_appt_{id} button in interactive message"
