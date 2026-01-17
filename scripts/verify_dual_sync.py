import datetime
import os
import sys
import unittest
from unittest.mock import MagicMock, patch

# Add app to path
sys.path.append(os.getcwd())

from app.core.database import SessionLocal
from app.models.models import Appointment, Barber, Business, Customer
from app.services.booking_service import BookingService


class TestDualSync(unittest.TestCase):
    def setUp(self):
        self.db = SessionLocal()
        self.service = BookingService(self.db)

        # Setup specific test data
        self.business = Business(name="DualSyncShop", phone_number_id="dual_sync_id", calendar_id="biz_cal_id")
        self.db.add(self.business)
        self.db.commit()

        self.barber = Barber(name="BarberSync", business_id=self.business.id, calendar_id="barber_cal_id")
        self.db.add(self.barber)
        self.db.commit()

        self.customer = Customer(phone="999888777", name="SyncTester")
        self.db.add(self.customer)
        self.db.commit()

    def tearDown(self):
        # Cleanup
        self.db.delete(self.customer)
        self.db.delete(self.barber)
        self.db.delete(self.business)
        self.db.commit()
        self.db.close()

    @patch("app.services.booking_service.calendar_service")
    def test_create_appointment_dual_sync(self, mock_calendar):
        print("\n--- Testing Dual Calendar Sync ---")

        # Mock successful creation returning an event dict with ID
        mock_calendar.create_event.side_effect = [{"id": "evt_barber"}, {"id": "evt_biz"}]

        date_str = "2023-12-25"
        time_str = "10:00"

        appt = self.service.create_appointment(self.customer, self.barber.id, date_str, time_str)

        # Verify calls
        # Expected: 2 calls to create_event
        self.assertEqual(mock_calendar.create_event.call_count, 2, "Should call create_event twice")

        calls = mock_calendar.create_event.call_args_list

        # Check Barber Call
        args_barber, _ = calls[0]
        self.assertEqual(args_barber[0], "barber_cal_id", "First call should be to barber calendar")

        # Check Business Call
        args_biz, _ = calls[1]
        self.assertEqual(args_biz[0], "biz_cal_id", "Second call should be to business calendar")

        print("PASS: Both calendars called successfully.")

    @patch("app.services.booking_service.calendar_service")
    def test_partial_failure_robustness(self, mock_calendar):
        print("\n--- Testing Robustness (Partial Failure) ---")

        # Scenario: Barber calendar fails, Business calendar should still try?
        # Current implementation: If barber fails (exception), it goes to 'except' block and skips business.
        # This test documents CURRENT behavior, then we'll fix it.

        mock_calendar.create_event.side_effect = [Exception("Google API Error"), {"id": "evt_biz"}]

        date_str = "2023-12-25"
        time_str = "12:00"

        appt = self.service.create_appointment(self.customer, self.barber.id, date_str, time_str)

        if mock_calendar.create_event.call_count == 1:
            print("OBSERVATION: Failure in first calendar sync blocked the second one (Current Behavior).")
        else:
            print("OBSERVATION: Robust sync achieved!")


if __name__ == "__main__":
    unittest.main()
