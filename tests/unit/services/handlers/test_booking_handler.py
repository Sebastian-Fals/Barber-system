"""
Tests: BookingHandler migrated to Evolution send_list.

Spec: booking-flow — Service Selection, Cancel Flow, send_list rows.
"""

import json
from unittest.mock import MagicMock, patch

from app.models.models import Barber, Business, Customer, CustomerData
from app.services.handlers.booking_handler import BookingHandler
from app.services.handlers.welcome_handler import WelcomeHandler


class TestBookingHandlerServiceSelection:
    """service_X interactive routes to barber selection via send_list."""

    def test_service_selection_transitions_to_select_barber(self):
        """User clicks service_1 -> state=SELECT_BARBER and send_list called."""
        db = MagicMock()
        business = Business(id=1, name="Test Biz")
        db.query.return_value.filter.return_value.first.return_value = business

        mock_barber = Barber(id=10, name="Carlos", business_id=1)
        mock_barber2 = Barber(id=11, name="Ana", business_id=1)

        customer = Customer(
            id=1,
            phone="+57000123",
            name="Test",
            conversation_state=CustomerData.SELECT_SERVICE,
            conversation_data="{}",
        )

        handler = BookingHandler(db, "test-instance", "test-apikey", business_id=1)

        with patch.object(handler, "barber_repo") as mock_barber_repo:
            mock_barber_repo.get_by_business.return_value = [mock_barber, mock_barber2]

            with patch.object(handler, "_update_state") as mock_update:
                with patch("app.services.handlers.base_handler.whatsapp_service") as mock_ws:
                    with patch("app.services.handlers.booking_handler.message_loader") as mock_loader:
                        mock_loader.get.return_value = "Elige barbero"

                        handler.handle_interactive(customer, "service_1", {})

                        mock_update.assert_called_once()
                        args, _kwargs = mock_update.call_args
                        assert args[1] == CustomerData.SELECT_BARBER

                        # verify send_list was called
                        mock_ws.send_list.assert_called_once()
                        rows = mock_ws.send_list.call_args[1].get("rows") or mock_ws.send_list.call_args[0][-1]
                        row_ids = [r["rowId"] for r in rows if r.get("rowId") != "cancel_flow"]
                        assert any(
                            rid.startswith("barber_") for rid in row_ids
                        ), f"Expected barber_ rows, got: {row_ids}"

    def test_invalid_service_selection_keeps_state(self):
        """Text not matching service -> returns False."""
        db = MagicMock()
        business = Business(id=1, name="Test Biz")
        db.query.return_value.filter.return_value.first.return_value = business

        customer = Customer(
            id=2,
            phone="+57000456",
            name="Test2",
            conversation_state=CustomerData.SELECT_SERVICE,
        )

        handler = BookingHandler(db, "test-instance", "test-apikey", business_id=1)
        result = handler.handle_message(customer, "algo random")
        assert result is False


class TestBookingHandlerCancelButtonEveryStep:
    """'Cancelar' row present in every booking step."""

    def test_cancel_row_in_service_step(self):
        """cancel_flow rowId included in send_list rows."""
        db = MagicMock()
        business = Business(id=1, name="Test Biz")
        db.query.return_value.filter.return_value.first.return_value = business

        customer = Customer(
            id=1,
            phone="+57000123",
            name="Test",
            conversation_state=CustomerData.SELECT_SERVICE,
            conversation_data="{}",
        )

        handler = BookingHandler(db, "test-instance", "test-apikey", business_id=1)

        with patch.object(handler, "barber_repo") as mock_barber_repo:
            mock_barber_repo.get_by_business.return_value = [Barber(id=10, name="Carlos", business_id=1)]

            with patch("app.services.handlers.base_handler.whatsapp_service") as mock_ws:
                with patch("app.services.handlers.booking_handler.message_loader") as mock_loader:
                    mock_loader.get.return_value = "Elige barbero"

                    handler.handle_interactive(customer, "service_1", {})

                    rows = mock_ws.send_list.call_args[1].get("rows") or mock_ws.send_list.call_args[0][-1]
                    cancel_ids = [r["rowId"] for r in rows if r["rowId"] == "cancel_flow"]
                    assert len(cancel_ids) == 1, f"Expected cancel_flow row, got: {rows}"

    def test_cancel_flow_resets_state(self):
        """cancel_flow interactive resets to IDLE."""
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

        handler = BookingHandler(db, "test-instance", "test-apikey", business_id=1)

        with patch.object(handler, "_update_state") as mock_update:
            handler.handle_interactive(customer, "cancel_flow", {})
            mock_update.assert_called_once()
            args, _kwargs = mock_update.call_args
            assert args[1] == CustomerData.IDLE
            assert args[2] == {}


class TestBookingHandlerCancel:
    """Cancel text detection unchanged."""

    def test_cancelar_text_during_booking_resets_to_idle(self):
        """Typed 'cancelar' resets state."""
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

        handler = BookingHandler(db, "test-instance", "test-apikey", business_id=1)
        with patch.object(handler, "_update_state") as mock_update:
            handler.handle_message(customer, "cancelar")
            mock_update.assert_called_once()
            args, kwargs = mock_update.call_args
            assert args[1] == CustomerData.IDLE
            assert args[2] == {}

    def test_cancelar_text_case_insensitive(self):
        """'Cancelar' (mixed case) resets."""
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

        handler = BookingHandler(db, "test-instance", "test-apikey", business_id=1)
        with patch.object(handler, "_update_state") as mock_update:
            handler.handle_message(customer, "Cancelar")
            mock_update.assert_called_once()
            args, _kwargs = mock_update.call_args
            assert args[1] == CustomerData.IDLE

    def test_non_cancel_text_not_handled_by_booking_handler(self):
        """Non-cancel text returns False."""
        db = MagicMock()
        business = Business(id=1, name="Test Biz")
        db.query.return_value.filter.return_value.first.return_value = business

        customer = Customer(
            id=3,
            phone="+57000789",
            name="Test3",
            conversation_state=CustomerData.SELECT_BARBER,
        )

        handler = BookingHandler(db, "test-instance", "test-apikey", business_id=1)
        result = handler.handle_message(customer, "quiero agendar")
        assert result is False


class TestWelcomeHandlerCancelButtons:
    """Cancel buttons in 'Mis Citas' list use send_list."""

    @patch("app.services.handlers.welcome_handler.message_loader")
    @patch("app.services.handlers.base_handler.whatsapp_service")
    @patch("app.services.handlers.welcome_handler.AppointmentRepository")
    def test_show_my_appointments_includes_cancel_rows(self, mock_repo_class, mock_ws, mock_loader):
        """send_list includes cancel_appt_{id} rowId."""
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

        mock_repo = MagicMock()
        mock_repo.get_active_for_customer.return_value = [mock_appt]
        mock_repo_class.return_value = mock_repo

        mock_loader.get.return_value = "Tus Citas"

        handler = WelcomeHandler(db, "test-instance", "test-apikey", business_id=1)
        customer = Customer(id=1, phone="+57000", name="Test")

        handler._show_my_appointments(customer)

        # verify send_list called with cancel row
        cancel_row_found = False
        for call in mock_ws.send_list.call_args_list:
            rows = call[1].get("rows") or call[0][-1]
            for r in rows:
                if "cancel_appt_" in r.get("rowId", ""):
                    cancel_row_found = True
                    break
        assert cancel_row_found, "Expected cancel_appt_{id} rowId in send_list"
