"""
RED tests: QueryHandler._smart_booking_transition uses interactive buttons.

Spec: booking-flow — AI and Non-AI Share Same UI.
Design: Both modes use identical interactive button payloads, LLM never generates UI.
"""

from unittest.mock import MagicMock, patch

from app.models.models import Business, Customer, CustomerData
from app.services.handlers.query_handler import QueryHandler


class TestQueryHandlerInteractiveButtons:
    """RED: _smart_booking_transition starts at SELECT_SERVICE with buttons."""

    @patch("app.services.handlers.query_handler.CustomerRepository")
    @patch("app.services.handlers.query_handler.BarberRepository")
    @patch("app.services.handlers.query_handler.AppointmentRepository")
    @patch("app.services.handlers.query_handler.BookingService")
    @patch("app.services.handlers.query_handler.whatsapp_service")
    @patch("app.services.handlers.query_handler.message_loader")
    def test_smart_booking_starts_at_select_service(
        self, mock_loader, mock_ws, mock_booking_svc, mock_appt_repo, mock_barber_repo_class, mock_cust_repo_class
    ):
        """
        Scenario: AI detects BOOK_APPOINTMENT intent with no entities.
        - GIVEN customer is in IDLE state and LLM returns BOOK_APPOINTMENT
        - WHEN _smart_booking_transition is called with empty extracted dict
        - THEN state is set to SELECT_SERVICE
        - AND service buttons are sent (interactive, not text).
        """
        from app.models.models import Service

        db = MagicMock()
        business = Business(id=1, name="Test Biz", ai_enabled=True)
        db.query.return_value.filter.return_value.first.return_value = business

        mock_barber_repo = MagicMock()
        mock_barber_repo.get_by_business.return_value = []
        mock_barber_repo_class.return_value = mock_barber_repo

        mock_cust_repo = MagicMock()
        mock_cust_repo.update_state = MagicMock()
        mock_cust_repo.update_data = MagicMock()
        mock_cust_repo_class.return_value = mock_cust_repo

        mock_appt_repo.return_value = MagicMock()
        mock_booking_svc.return_value = MagicMock()
        mock_loader.get.return_value = "Elige un servicio"

        handler = QueryHandler(db, "phone_id_123", business_id=1)
        customer = Customer(
            id=1,
            phone="+57000",
            name="Test",
            conversation_state=CustomerData.IDLE,
            conversation_data="{}",
        )

        with patch("app.features.business.service_repository.ServiceRepository") as mock_svc_repo_class:
            svc1 = Service(id=1, business_id=1, name="Corte", duration_minutes=30)
            svc2 = Service(id=2, business_id=1, name="Barba", duration_minutes=45)
            mock_svc_repo = MagicMock()
            mock_svc_repo.get_by_business.return_value = [svc1, svc2]
            mock_svc_repo_class.return_value = mock_svc_repo

            handler._smart_booking_transition(customer, {}, "¡Claro! Vamos a agendar.")

            # Verify state was updated to SELECT_SERVICE
            state_calls = mock_cust_repo.update_state.call_args_list
            assert len(state_calls) >= 1, f"Expected update_state to be called at least once, got {len(state_calls)}"
            assert (
                state_calls[0][0][1] == CustomerData.SELECT_SERVICE
            ), f"Expected SELECT_SERVICE, got {state_calls[0][0][1] if state_calls else 'none'}"

            # Verify interactive buttons were sent (not plain text)
            mock_ws.send_interactive_button.assert_called_once()
            args, kwargs = mock_ws.send_interactive_button.call_args
            if len(args) >= 4:
                buttons = args[3]
            else:
                buttons = kwargs.get("buttons", [])

            button_ids = [b["id"] for b in buttons]
            assert any(
                bid.startswith("service_") for bid in button_ids
            ), f"Expected service_ buttons, got: {button_ids}"

    @patch("app.services.handlers.query_handler.CustomerRepository")
    @patch("app.services.handlers.query_handler.BarberRepository")
    @patch("app.services.handlers.query_handler.AppointmentRepository")
    @patch("app.services.handlers.query_handler.BookingService")
    @patch("app.services.handlers.query_handler.whatsapp_service")
    @patch("app.services.handlers.query_handler.message_loader")
    def test_smart_booking_ai_and_non_ai_use_same_button_ids(
        self, mock_loader, mock_ws, mock_booking_svc, mock_appt_repo, mock_barber_repo_class, mock_cust_repo_class
    ):
        """
        Scenario: AI and non-AI modes use identical button payloads.
        - GIVEN AI mode presents service selection
        - WHEN the buttons are generated
        - THEN they share the same prefix (service_) and same structure.
        """
        from app.models.models import Service

        db = MagicMock()
        business = Business(id=1, name="Test Biz", ai_enabled=True)
        db.query.return_value.filter.return_value.first.return_value = business

        mock_barber_repo = MagicMock()
        mock_barber_repo.get_by_business.return_value = []
        mock_barber_repo_class.return_value = mock_barber_repo

        mock_cust_repo = MagicMock()
        mock_cust_repo.update_state = MagicMock()
        mock_cust_repo.update_data = MagicMock()
        mock_cust_repo_class.return_value = mock_cust_repo

        mock_appt_repo.return_value = MagicMock()
        mock_booking_svc.return_value = MagicMock()
        mock_loader.get.return_value = "Elige un servicio"

        handler = QueryHandler(db, "phone_id_123", business_id=1)
        customer = Customer(
            id=1,
            phone="+57000",
            name="Test",
            conversation_state=CustomerData.IDLE,
            conversation_data="{}",
        )

        with patch("app.features.business.service_repository.ServiceRepository") as mock_svc_repo_class:
            svc = Service(id=1, business_id=1, name="Corte", duration_minutes=30)
            mock_svc_repo = MagicMock()
            mock_svc_repo.get_by_business.return_value = [svc]
            mock_svc_repo_class.return_value = mock_svc_repo

            handler._smart_booking_transition(customer, {}, "Vamos a agendar")

            # The button structure must match: {id: "service_X", title: name}
            mock_ws.send_interactive_button.assert_called_once()
            args, kwargs = mock_ws.send_interactive_button.call_args
            if len(args) >= 4:
                buttons = args[3]
            else:
                buttons = kwargs.get("buttons", [])

            for btn in buttons:
                if btn["id"] == "cancel_flow":
                    continue
                assert "id" in btn, f"Button missing 'id': {btn}"
                assert "title" in btn, f"Button missing 'title': {btn}"
                assert btn["id"].startswith("service_"), f"Expected service_ prefix, got: {btn['id']}"


class TestQueryHandlerIntents:
    """RED: PROVIDE_NAME and FALLBACK intents handled."""

    @patch("app.services.handlers.query_handler.CustomerRepository")
    @patch("app.services.handlers.query_handler.BarberRepository")
    @patch("app.services.handlers.query_handler.BusinessRepository")
    @patch("app.services.handlers.query_handler.AppointmentRepository")
    @patch("app.services.handlers.query_handler.BookingService")
    @patch("app.services.handlers.query_handler.whatsapp_service")
    def test_provide_name_intent_updates_customer_name(
        self,
        mock_ws,
        mock_booking_svc,
        mock_appt_repo,
        mock_biz_repo_class,
        mock_barber_repo_class,
        mock_cust_repo_class,
    ):
        """
        Scenario: LLM returns PROVIDE_NAME intent with extracted name.
        - GIVEN customer sends "Me llamo Juan"
        - WHEN LLM returns intent=PROVIDE_NAME with extracted name "Juan"
        - THEN customer name is updated and a friendly reply is sent.
        """
        db = MagicMock()
        business = Business(id=1, name="Test Biz", ai_enabled=True)
        db.query.return_value.filter.return_value.first.return_value = business

        mock_barber_repo = MagicMock()
        mock_barber_repo.get_by_business.return_value = []
        mock_barber_repo_class.return_value = mock_barber_repo

        mock_biz_repo = MagicMock()
        mock_biz_repo.get_by_id.return_value = business
        mock_biz_repo_class.return_value = mock_biz_repo

        mock_cust_repo = MagicMock()
        mock_cust_repo.update = MagicMock()
        mock_cust_repo.update_state = MagicMock()
        mock_cust_repo_class.return_value = mock_cust_repo

        mock_appt_repo.return_value = MagicMock()
        mock_booking_svc.return_value = MagicMock()

        # Mock LLM response
        with patch("app.services.handlers.query_handler.llm_service") as mock_llm:
            mock_llm.analyze_message.return_value = {
                "intent": "PROVIDE_NAME",
                "reply": "¡Encantado, Juan!",
                "extracted": {"customer_name": "Juan"},
            }

            handler = QueryHandler(db, "phone_id_123", business_id=1)
            customer = Customer(
                id=1,
                phone="+57000",
                name="Usuario",
                conversation_state=CustomerData.IDLE,
                conversation_data="{}",
            )

            with patch.object(handler, "_manage_history_expiration"):
                with patch.object(handler, "_log_message"):
                    handler.handle_message(customer, "Me llamo Juan")

            # Name should have been updated
            assert mock_cust_repo.update.called, "Expected customer.update to be called"
            update_call = mock_cust_repo.update.call_args
            if update_call:
                name_value = update_call[1].get("name") if len(update_call[0]) < 2 else update_call[0][1].get("name")
                assert name_value == "Juan", f"Expected name 'Juan', got '{name_value}'"

    @patch("app.services.handlers.query_handler.CustomerRepository")
    @patch("app.services.handlers.query_handler.BarberRepository")
    @patch("app.services.handlers.query_handler.BusinessRepository")
    @patch("app.services.handlers.query_handler.AppointmentRepository")
    @patch("app.services.handlers.query_handler.BookingService")
    @patch("app.services.handlers.query_handler.whatsapp_service")
    def test_fallback_intent_sends_helpful_message(
        self,
        mock_ws,
        mock_booking_svc,
        mock_appt_repo,
        mock_biz_repo_class,
        mock_barber_repo_class,
        mock_cust_repo_class,
    ):
        """
        Scenario: LLM cannot determine intent, returns FALLBACK or UNKNOWN.
        - GIVEN customer sends gibberish
        - WHEN LLM returns intent=FALLBACK with a helpful reply
        - THEN a message is sent to the user.
        """
        db = MagicMock()
        business = Business(id=1, name="Test Biz", ai_enabled=True)
        db.query.return_value.filter.return_value.first.return_value = business

        mock_barber_repo = MagicMock()
        mock_barber_repo.get_by_business.return_value = []
        mock_barber_repo_class.return_value = mock_barber_repo

        mock_biz_repo = MagicMock()
        mock_biz_repo.get_by_id.return_value = business
        mock_biz_repo_class.return_value = mock_biz_repo

        mock_cust_repo = MagicMock()
        mock_cust_repo_class.return_value = mock_cust_repo

        mock_appt_repo.return_value = MagicMock()
        mock_booking_svc.return_value = MagicMock()

        with patch("app.services.handlers.query_handler.llm_service") as mock_llm:
            mock_llm.analyze_message.return_value = {
                "intent": "FALLBACK",
                "reply": "No entendí bien. ¿Puedes usar el menú?",
            }

            handler = QueryHandler(db, "phone_id_123", business_id=1)
            customer = Customer(
                id=1,
                phone="+57000",
                name="Test",
                conversation_state=CustomerData.IDLE,
                conversation_data="{}",
            )

            with patch.object(handler, "_manage_history_expiration"):
                with patch.object(handler, "_log_message"):
                    handler.handle_message(customer, "asdfghjkl")

            assert mock_ws.send_message.called, "Expected a message to be sent for FALLBACK intent"
