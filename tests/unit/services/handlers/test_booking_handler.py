"""
RED tests: Cancel flow in BookingHandler + cancel buttons + service selection.

Spec: booking-flow — Service Selection Step, Unified Booking Flow, Cancel mid-flow.
"""
import json
from unittest.mock import MagicMock, patch

from app.models.models import Business, Customer, CustomerData
from app.services.handlers.booking_handler import BookingHandler
from app.services.handlers.welcome_handler import WelcomeHandler


class TestBookingHandlerServiceSelection:
    """RED: service_X interactive routes to barber selection."""

    def test_service_selection_transitions_to_select_barber(self):
        """
        Scenario: User clicks a service button.
        - GIVEN customer is in SELECT_SERVICE state with empty data
        - WHEN interactive_id "service_1" is received
        - THEN state becomes SELECT_BARBER and barber buttons are sent.
        """
        db = MagicMock()
        business = Business(id=1, name="Test Biz")
        db.query.return_value.filter.return_value.first.return_value = business

        from app.models.models import Barber

        mock_barber = Barber(id=10, name="Carlos", business_id=1)
        mock_barber2 = Barber(id=11, name="Ana", business_id=1)

        customer = Customer(
            id=1,
            phone="+57000123",
            name="Test",
            conversation_state=CustomerData.SELECT_SERVICE,
            conversation_data="{}",
        )

        handler = BookingHandler(db, "phone_id_123", business_id=1)

        # Mock barber repo to return barbers
        with patch.object(handler, "barber_repo") as mock_barber_repo:
            mock_barber_repo.get_by_business.return_value = [mock_barber, mock_barber2]

            with patch.object(handler, "_update_state") as mock_update:
                with patch("app.services.handlers.booking_handler.whatsapp_service") as mock_ws:
                    with patch("app.services.handlers.booking_handler.message_loader") as mock_loader:
                        mock_loader.get.return_value = "Elige barbero"

                        handler.handle_interactive(customer, "service_1", {})

                        # Verify state transition to SELECT_BARBER
                        mock_update.assert_called_once()
                        args, _kwargs = mock_update.call_args
                        assert args[1] == CustomerData.SELECT_BARBER

                        # Verify barber buttons were sent
                        mock_ws.send_interactive_button.assert_called_once()
                        ws_args, ws_kwargs = mock_ws.send_interactive_button.call_args
                        if len(ws_args) >= 4:
                            buttons = ws_args[3]
                        else:
                            buttons = ws_kwargs.get("buttons", [])
                        button_ids = [b["id"] for b in buttons]
                        assert any(
                            bid.startswith("barber_") for bid in button_ids
                        ), f"Expected barber_ buttons, got: {button_ids}"

    def test_invalid_service_selection_keeps_state(self):
        """
        Scenario: User sends text that doesn't match a service.
        - GIVEN customer is in SELECT_SERVICE state
        - WHEN text "algo random" is sent (not matching any service)
        - THEN BookingHandler stays in SELECT_SERVICE (returns False for fallthrough).
        """
        db = MagicMock()
        business = Business(id=1, name="Test Biz")
        db.query.return_value.filter.return_value.first.return_value = business

        customer = Customer(
            id=2,
            phone="+57000456",
            name="Test2",
            conversation_state=CustomerData.SELECT_SERVICE,
        )

        handler = BookingHandler(db, "phone_id_123", business_id=1)
        result = handler.handle_message(customer, "algo random")

        # Should return False (not handled) so conversation_service can re-prompt
        assert result is False


class TestBookingHandlerCancelButtonEveryStep:
    """RED: "Cancelar" button present in every booking step."""

    def test_cancel_button_in_service_step(self):
        """
        - GIVEN customer is in SELECT_SERVICE
        - WHEN service buttons are presented
        - THEN a "Cancelar" button with id=cancel_flow is included.
        """
        db = MagicMock()
        business = Business(id=1, name="Test Biz")
        db.query.return_value.filter.return_value.first.return_value = business

        from app.models.models import Barber

        customer = Customer(
            id=1,
            phone="+57000123",
            name="Test",
            conversation_state=CustomerData.SELECT_SERVICE,
            conversation_data="{}",
        )

        handler = BookingHandler(db, "phone_id_123", business_id=1)

        with patch.object(handler, "barber_repo") as mock_barber_repo:
            mock_barber_repo.get_by_business.return_value = [Barber(id=10, name="Carlos", business_id=1)]

            with patch("app.services.handlers.booking_handler.whatsapp_service") as mock_ws:
                with patch("app.services.handlers.booking_handler.message_loader") as mock_loader:
                    mock_loader.get.return_value = "Elige barbero"

                    handler.handle_interactive(customer, "service_1", {})

                    ws_args, ws_kwargs = mock_ws.send_interactive_button.call_args
                    if len(ws_args) >= 4:
                        buttons = ws_args[3]
                    else:
                        buttons = ws_kwargs.get("buttons", [])

                    cancel_ids = [b["id"] for b in buttons if b["id"] == "cancel_flow"]
                    assert len(cancel_ids) == 1, f"Expected cancel_flow button in step, got buttons: {buttons}"

    def test_cancel_flow_interactive_resets_state(self):
        """
        - GIVEN customer is in any booking state
        - WHEN interactive_id "cancel_flow" is received
        - THEN state resets to IDLE and welcome menu is shown.
        """
        db = MagicMock()
        business = Business(id=1, name="Test Biz")
        db.query.return_value.filter.return_value.first.return_value = business

        customer = Customer(
            id=1,
            phone="+57000123",
            name="Test",
            conversation_state=CustomerData.SELECT_SERVICE,
            conversation_data=json.dumps({"service_id": 1}),
        )

        handler = BookingHandler(db, "phone_id_123", business_id=1)

        with patch.object(handler, "_update_state") as mock_update:
            handler.handle_interactive(customer, "cancel_flow", {})

            mock_update.assert_called_once()
            args, _kwargs = mock_update.call_args
            assert args[1] == CustomerData.IDLE
            assert args[2] == {}


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
