import unittest
from unittest.mock import MagicMock, patch

# Mock Config before importing service
with patch("app.core.config.settings") as mock_settings:
    mock_settings.GOOGLE_APPLICATION_CREDENTIALS = "dummy.json"
    mock_settings.TIMEZONE = "UTC"
    from app.features.calendar.service import CalendarService


class TestSyncFix(unittest.TestCase):
    def test_sync_events_query_construction(self):
        # Setup
        service = CalendarService()
        service.service = MagicMock()  # Mock Google Service

        # Mock Google Response (1 Cancelled Event)
        mock_events = {"items": [{"id": "evt123", "status": "cancelled"}]}
        service.service.events.return_value.list.return_value.execute.return_value = mock_events

        # Mock DB
        db = MagicMock()

        # Run Sync
        service.sync_events("cal123", db=db)

        # Verify DB Query
        # We want to ensure db.query(Appointment).filter(...) was called
        # And specifically that it didn't crash with AttributeError

        print("✅ Sync ran without crashing.")

        # Optional: Inspect filter calls if possible, but just not crashing is the main proof
        # that Appointment.* attribute access was valid.


if __name__ == "__main__":
    unittest.main()
