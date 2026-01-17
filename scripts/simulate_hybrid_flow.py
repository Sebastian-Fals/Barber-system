import os
import sys
import unittest
from unittest.mock import MagicMock, patch

# Add app to path
sys.path.append(os.getcwd())

from app.core.database import SessionLocal
from app.models.models import Business, Customer, CustomerData
from app.services.conversation_service import ConversationService


class TestHybridFlow(unittest.TestCase):
    def setUp(self):
        self.db = SessionLocal()
        # Ensure a test business exists
        self.phone_id = "test_phone_id"
        self.business = self.db.query(Business).filter(Business.phone_number_id == self.phone_id).first()
        if not self.business:
            self.business = Business(name="Test Barber", phone_number_id=self.phone_id, ai_enabled=True)
            self.db.add(self.business)
            self.db.commit()

        self.customer_phone = "5551234567"

        # Reset customer
        cust = self.db.query(Customer).filter(Customer.phone == self.customer_phone).first()
        if cust:
            self.db.delete(cust)
            self.db.commit()

        self.service = ConversationService(self.db, self.phone_id)

    def tearDown(self):
        self.db.close()

    @patch("app.services.conversation_service.whatsapp_service")
    def test_deterministic_fallback(self, mock_whatsapp):
        print("\n--- Testing Deterministic Fallback (AI Disabled) ---")
        # Disable AI
        self.business.ai_enabled = False
        self.db.commit()

        # User sends non-keyword
        self.service.handle_incoming_message(self.customer_phone, "quiero una pizza")

        # Verify Fallback was sent
        args, _ = mock_whatsapp.send_interactive_button.call_args
        print(f"Call args: {args}")
        self.assertIn("Para ayudarte, por favor selecciona", args[2])  # Message body

    @patch("app.services.conversation_service.whatsapp_service")
    def test_keyword_override(self, mock_whatsapp):
        print("\n--- Testing Keyword Override (AI Disabled) ---")
        self.business.ai_enabled = False
        self.db.commit()

        self.service.handle_incoming_message(self.customer_phone, "menu")

        # Verify Welcome Menu
        args, _ = mock_whatsapp.send_interactive_button.call_args
        self.assertIn("Bienvenido a *Test Barber*", args[2])

    @patch("app.services.conversation_service.llm_service")
    @patch("app.services.conversation_service.whatsapp_service")
    def test_ai_flow(self, mock_whatsapp, mock_llm):
        print("\n--- Testing AI Flow (AI Enabled) ---")
        self.business.ai_enabled = True
        self.db.commit()

        # Mock LLM Response
        mock_llm.analyze_message.return_value = {
            "intent": "CHITCHAT",
            "reply": "Hola! Soy tu asistente virtual.",
            "extracted": {},
        }

        self.service.handle_incoming_message(self.customer_phone, "Hola robot")

        # Verify LLM Reply
        mock_whatsapp.send_message.assert_called_with(
            self.phone_id, self.customer_phone, "Hola! Soy tu asistente virtual."
        )


if __name__ == "__main__":
    unittest.main()
