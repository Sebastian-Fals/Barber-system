"""
Tests: QueryHandler migrated to Evolution send_list.

Spec: booking-flow — AI and Non-AI Share Same UI.
Design: Both modes use send_list with rowId-based selection.
"""

from unittest.mock import MagicMock, patch

from app.models.models import Business, Customer, CustomerData
from app.services.handlers.query_handler import QueryHandler


class TestQueryHandlerInteractiveLists:
    """_smart_booking_transition sends send_list rows."""

    @patch("app.services.handlers.query_handler.CustomerRepository")
    @patch("app.services.handlers.query_handler.BarberRepository")
    @patch("app.services.handlers.query_handler.AppointmentRepository")
    @patch("app.services.handlers.query_handler.BookingService")
    @patch("app.services.handlers.base_handler.whatsapp_service")
    @patch("app.services.handlers.query_handler.message_loader")
    def test_smart_booking_starts_at_select_service(
        self, mock_loader, mock_ws, mock_booking_svc, mock_appt_repo, mock_barber_repo_class, mock_cust_repo_class
    ):
        """
        Scenario: AI detects BOOK_APPOINTMENT with no entities.
        - GIVEN IDLE state, LLM returns BOOK_APPOINTMENT
        - WHEN _smart_booking_transition with empty extracted
        - THEN state=SELECT_SERVICE, send_list with service_ rows.
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

        handler = QueryHandler(db, "test-instance", "test-apikey", business_id=1)
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

            state_calls = mock_cust_repo.update_state.call_args_list
            assert len(state_calls) >= 1
            assert state_calls[0][0][1] == CustomerData.SELECT_SERVICE

            mock_ws.send_list.assert_called_once()
            rows = mock_ws.send_list.call_args[1].get("rows") or mock_ws.send_list.call_args[0][-1]
            row_ids = [r["rowId"] for r in rows if r.get("rowId") != "cancel_flow"]
            assert any(rid.startswith("service_") for rid in row_ids), f"Expected service_ rows, got: {row_ids}"

    @patch("app.services.handlers.query_handler.CustomerRepository")
    @patch("app.services.handlers.query_handler.BarberRepository")
    @patch("app.services.handlers.query_handler.AppointmentRepository")
    @patch("app.services.handlers.query_handler.BookingService")
    @patch("app.services.handlers.base_handler.whatsapp_service")
    @patch("app.services.handlers.query_handler.message_loader")
    def test_smart_booking_button_ids_use_same_rowid_prefix(
        self, mock_loader, mock_ws, mock_booking_svc, mock_appt_repo, mock_barber_repo_class, mock_cust_repo_class
    ):
        """AI and non-AI modes share same rowId prefixes."""
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

        handler = QueryHandler(db, "test-instance", "test-apikey", business_id=1)
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

            mock_ws.send_list.assert_called_once()
            rows = mock_ws.send_list.call_args[1].get("rows") or mock_ws.send_list.call_args[0][-1]
            for r in rows:
                if r["rowId"] == "cancel_flow":
                    continue
                assert "rowId" in r, f"Row missing rowId: {r}"
                assert r["rowId"].startswith("service_"), f"Expected service_ prefix: {r['rowId']}"


class TestQueryHandlerIntents:
    """PROVIDE_NAME and FALLBACK intents unchanged — text messages, no send_list."""

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
        """PROVIDE_NAME updates customer name and sends reply."""
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

        with patch("app.services.handlers.query_handler.llm_service") as mock_llm:
            mock_llm.analyze_message.return_value = {
                "intent": "PROVIDE_NAME",
                "reply": "¡Encantado, Juan!",
                "extracted": {"customer_name": "Juan"},
            }

            handler = QueryHandler(db, "test-instance", "test-apikey", business_id=1)
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

            assert mock_cust_repo.update.called
            update_call = mock_cust_repo.update.call_args
            if update_call:
                name_value = update_call[1].get("name") if len(update_call[0]) < 2 else update_call[0][1].get("name")
                assert name_value == "Juan"

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
        """FALLBACK intent sends a helpful text message."""
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

            handler = QueryHandler(db, "test-instance", "test-apikey", business_id=1)
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

            assert mock_ws.send_message.called
