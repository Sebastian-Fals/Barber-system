"""
RED tests: WelcomeHandler._start_booking_flow transitions to SELECT_SERVICE.

Spec: booking-flow — Service Selection Step, Unified Booking Flow Order.
Design: _start_booking_flow shows service buttons instead of barber buttons.
"""

from unittest.mock import MagicMock, patch

from app.models.models import Business, Customer, CustomerData
from app.services.handlers.welcome_handler import WelcomeHandler


class TestWelcomeHandlerServiceSelection:
    """RED: _start_booking_flow sends service buttons, state=SELECT_SERVICE."""

    @patch("app.features.customers.repository.CustomerRepository")
    @patch("app.features.business.service_repository.ServiceRepository")
    @patch("app.features.business.barber_repository.BarberRepository")
    @patch("app.services.handlers.welcome_handler.AppointmentRepository")
    @patch("app.services.handlers.welcome_handler.whatsapp_service")
    @patch("app.services.handlers.welcome_handler.message_loader")
    def test_start_booking_flow_sends_service_buttons(
        self, mock_loader, mock_ws, mock_appt_repo, mock_barber_repo_class, mock_svc_repo_class, mock_cust_repo_class
    ):
        """
        Scenario: User clicks "Agendar Cita" (menu_book).
        - GIVEN customer is in IDLE state
        - WHEN _start_booking_flow is called
        - THEN state is set to SELECT_SERVICE
        - AND service buttons are sent (not barber buttons).
        """
        from app.models.models import Service

        db = MagicMock()
        business = Business(id=1, name="Test Biz")
        db.query.return_value.filter.return_value.first.return_value = business

        # Mock repositories
        mock_barber_repo = MagicMock()
        mock_barber_repo.get_by_business.return_value = []
        mock_barber_repo_class.return_value = mock_barber_repo

        svc1 = Service(id=1, business_id=1, name="Corte", duration_minutes=30)
        svc2 = Service(id=2, business_id=1, name="Barba", duration_minutes=45)
        mock_svc_repo = MagicMock()
        mock_svc_repo.get_by_business.return_value = [svc1, svc2]
        mock_svc_repo_class.return_value = mock_svc_repo

        mock_cust = MagicMock()
        mock_cust.update_state = MagicMock()
        mock_cust_repo_class.return_value = mock_cust

        mock_appt_repo.return_value = MagicMock()
        mock_loader.get.return_value = "Elige un servicio"

        handler = WelcomeHandler(db, "phone_id_123", business_id=1)
        customer = Customer(id=1, phone="+57000", name="Test")
        handler._start_booking_flow(customer)

        # Verify state set to SELECT_SERVICE
        assert mock_cust.update_state.call_count >= 1
        called_state = mock_cust.update_state.call_args[0][1]
        assert called_state == CustomerData.SELECT_SERVICE, f"Expected SELECT_SERVICE but got {called_state}"

        # Verify send_interactive_button was called with service buttons
        mock_ws.send_interactive_button.assert_called_once()
        args, kwargs = mock_ws.send_interactive_button.call_args
        if len(args) >= 4:
            buttons = args[3]
        else:
            buttons = kwargs.get("buttons", [])

        button_ids = [b["id"] for b in buttons]
        assert any(
            bid.startswith("service_") for bid in button_ids
        ), f"Expected service_ prefix buttons, got: {button_ids}"
        assert "service_1" in button_ids
        assert "service_2" in button_ids

    @patch("app.features.customers.repository.CustomerRepository")
    @patch("app.features.business.service_repository.ServiceRepository")
    @patch("app.features.business.barber_repository.BarberRepository")
    @patch("app.services.handlers.welcome_handler.AppointmentRepository")
    @patch("app.services.handlers.welcome_handler.whatsapp_service")
    @patch("app.services.handlers.welcome_handler.message_loader")
    def test_start_booking_flow_no_services_fallback(
        self, mock_loader, mock_ws, mock_appt_repo, mock_barber_repo_class, mock_svc_repo_class, mock_cust_repo_class
    ):
        """
        Scenario: No services configured for the business.
        - GIVEN business has no services in DB
        - WHEN _start_booking_flow is called
        - THEN a fallback message is sent instead of empty buttons.
        """
        db = MagicMock()
        business = Business(id=1, name="Test Biz")
        db.query.return_value.filter.return_value.first.return_value = business

        mock_barber_repo = MagicMock()
        mock_barber_repo.get_by_business.return_value = []
        mock_barber_repo_class.return_value = mock_barber_repo

        mock_svc_repo = MagicMock()
        mock_svc_repo.get_by_business.return_value = []
        mock_svc_repo_class.return_value = mock_svc_repo

        mock_cust = MagicMock()
        mock_cust.update_state = MagicMock()
        mock_cust_repo_class.return_value = mock_cust

        mock_appt_repo.return_value = MagicMock()
        mock_loader.get.return_value = "No hay servicios"

        handler = WelcomeHandler(db, "phone_id_123", business_id=1)
        customer = Customer(id=1, phone="+57000", name="Test")
        handler._start_booking_flow(customer)

        # Should still update state to SELECT_SERVICE
        assert mock_cust.update_state.call_count >= 1
        assert mock_cust.update_state.call_args[0][1] == CustomerData.SELECT_SERVICE

        # A message should be sent (not interactive buttons for empty list)
        assert mock_ws.send_message.called or mock_ws.send_interactive_button.called
