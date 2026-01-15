
import sys
import os
import unittest
from unittest.mock import MagicMock, patch
import datetime

# Add app to path
sys.path.append(os.getcwd())

from app.services.conversation_service import ConversationService
from app.core.database import SessionLocal
from app.models.models import Business, Customer, Barber, CustomerData

class TestFixes(unittest.TestCase):
    def setUp(self):
        self.db = SessionLocal()
        self.phone_id = "test_verification_id"
        
        # Ensure business
        self.business = self.db.query(Business).filter(Business.phone_number_id == self.phone_id).first()
        if not self.business:
            self.business = Business(name="FixVerifyShop", phone_number_id=self.phone_id, ai_enabled=True)
            self.db.add(self.business)
            self.db.commit()

        # Ensure barber "Juan Perez"
        self.barber = self.db.query(Barber).filter(Barber.name == "Juan Perez", Barber.business_id == self.business.id).first()
        if not self.barber:
            self.barber = Barber(name="Juan Perez", business_id=self.business.id)
            self.db.add(self.barber)
            self.db.commit()

        self.customer_phone = "5559876543"
        # ensure customer
        customer = self.db.query(Customer).filter(Customer.phone == self.customer_phone).first()
        if not customer:
            customer = Customer(phone=self.customer_phone, name="Tester")
            self.db.add(customer)
            self.db.commit()
            
        self.service = ConversationService(self.db, self.phone_id)

    def tearDown(self):
        self.db.close()

    @patch('app.services.conversation_service.whatsapp_service')
    @patch('app.services.conversation_service.llm_service')
    def test_loose_barber_match(self, mock_llm, mock_whatsapp):
        print("\n--- Testing Loose Barber Name Matching ---")
        
        # Scenario: user says "quiero con juan"
        mock_llm.analyze_message.return_value = {
            "intent": "BOOK_APPOINTMENT",
            "extracted": {
                "barber_name": "juan", # Lowercase, partial
                "date": "2023-12-25"
            },
            "reply": "Checking..."
        }
        
        # Mock get_available_slots to avoid real DB/Calendar calls
        with patch.object(self.service.booking_service, 'get_available_slots', return_value=[]):
             self.service.handle_incoming_message(self.customer_phone, "cita con juan")

        # Check calls
        msg_calls = mock_whatsapp.send_message.call_args_list
        button_calls = mock_whatsapp.send_interactive_button.call_args_list
        
        combined = str(msg_calls) + str(button_calls)
        
        if "Con qué profesional" in combined:
            print("FAIL: It asked to select a barber, meaning match failed.")
            self.fail("Barber match failed")
        else:
            print("PASS: Barber matched successfully (did not ask to select barber).")
            
        # Assertion: "Lo siento" should be present because slots=[] and date was provided
        found_message = any("Lo siento" in str(c) for c in msg_calls)
        self.assertTrue(found_message, "Should have reached availability check, impling barber was found.")

    @patch('app.services.conversation_service.whatsapp_service')
    @patch('app.services.conversation_service.llm_service')
    def test_empathetic_date_error(self, mock_llm, mock_whatsapp):
        print("\n--- Testing Empathetic Date Error ---")
        
        mock_llm.analyze_message.return_value = {
            "intent": "BOOK_APPOINTMENT",
            "extracted": {
                "barber_name": "Juan Perez", 
                "date": "invalid-date" # Malformed
            },
            "reply": "check"
        }
        
        self.service.handle_incoming_message(self.customer_phone, "cita el dia rarito")
        
        # Verify the specific error message
        mock_whatsapp.send_message.assert_called()
        args, _ = mock_whatsapp.send_message.call_args
        self.assertIn("Ups, esa fecha no se ve bien", args[2])
        print("PASS: Empathetic error message verified.")

    @patch('app.services.conversation_service.whatsapp_service')
    @patch('app.services.conversation_service.llm_service')
    def test_availability_time_period(self, mock_llm, mock_whatsapp):
        print("\n--- Testing Time Period Filtering ---")
        
        target_date = datetime.date(2023, 12, 1)
        
        # Mock slots: 9am, 11am (morning), 15pm, 17pm (afternoon)
        slots = [
            datetime.datetime(2023, 12, 1, 9, 0),
            datetime.datetime(2023, 12, 1, 11, 0),
            datetime.datetime(2023, 12, 1, 15, 0),
            datetime.datetime(2023, 12, 1, 17, 0)
        ]
        
        mock_llm.analyze_message.return_value = {
            "intent": "BOOK_APPOINTMENT",
            "extracted": {
                "barber_name": "Juan Perez",
                "date": "2023-12-01",
                "time_period": "tarde" # Afternoon
            },
            "reply": "check"
        }
        
        with patch.object(self.service.booking_service, 'get_available_slots', return_value=slots):
             self.service.handle_incoming_message(self.customer_phone, "por la tarde")
             
        # It should send a menu with slots.
        # Verify the slots presented are only 15:00 and 17:00
        button_calls = mock_whatsapp.send_interactive_button.call_args_list
        # The last call should be the slot menu
        if not button_calls:
             self.fail("No buttons sent for slots")
             
        args, _ = button_calls[-1]
        buttons = args[3] # 4th arg is buttons
        
        button_titles = [b['title'] for b in buttons]
        # print(f"Presented slots: {button_titles}")
        
        self.assertIn("3:00pm", button_titles)
        self.assertIn("5:00pm", button_titles)
        self.assertNotIn("9:00am", button_titles)
        self.assertNotIn("11:00am", button_titles)
        print("PASS: Time period filtered correctly.")

if __name__ == '__main__':
    unittest.main()
