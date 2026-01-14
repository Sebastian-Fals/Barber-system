import os
import datetime
from google.oauth2 import service_account
from googleapiclient.discovery import build
from app.core.config import settings

class CalendarService:
    SCOPES = ['https://www.googleapis.com/auth/calendar']

    def __init__(self):
        self.creds = None
        self.service = None
        self._authenticate()

    def _authenticate(self):
        if os.path.exists(settings.GOOGLE_APPLICATION_CREDENTIALS):
            self.creds = service_account.Credentials.from_service_account_file(
                settings.GOOGLE_APPLICATION_CREDENTIALS, scopes=self.SCOPES
            )
            self.service = build('calendar', 'v3', credentials=self.creds)
        else:
            print("Warning: Google Credentials file not found. Calendar service will not work.")

    def create_event(self, calendar_id: str, summary: str, start_time: datetime.datetime, end_time: datetime.datetime, description: str = ""):
        """
        Creates an event in the specified calendar.
        """
        if not self.service:
            return None

        event = {
            'summary': summary,
            'description': description,
            'start': {
                'dateTime': start_time.isoformat(),
                'timeZone': settings.TIMEZONE, 
            },
            'end': {
                'dateTime': end_time.isoformat(),
                'timeZone': settings.TIMEZONE,
            },
        }

        try:
            event = self.service.events().insert(calendarId=calendar_id, body=event).execute()
            print(f"Event created: {event.get('htmlLink')}")
            return event.get('id')
        except Exception as e:
            print(f"An error occurred: {e}")
            return None

    def get_busy_slots(self, calendar_id: str, start_time: datetime.datetime, end_time: datetime.datetime):
        """
        Returns a list of busy time ranges (start, end) for the given period.
        """
        if not self.service:
            print("Service not initialized")
            return []

        try:
            print(f"Checking gcal for {calendar_id} from {start_time} to {end_time}")
            events_result = self.service.events().list(
                calendarId=calendar_id,
                timeMin=start_time.isoformat() + 'Z',
                timeMax=end_time.isoformat() + 'Z',
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            
            items = events_result.get('items', [])
            busy_slots = []
            
            for event in items:
                # Handle 'date' (all day) vs 'dateTime'
                start = event['start'].get('dateTime', event['start'].get('date'))
                end = event['end'].get('dateTime', event['end'].get('date'))
                
                # Simple parsing (assuming ISO format from Google)
                # Note: Google returns timezone offset, we need to handle that. 
                # For MVP, we'll treat strings basically.
                busy_slots.append((start, end))
                
            print(f"Found {len(busy_slots)} busy slots")
            return busy_slots
        except Exception as e:
            print(f"Error checking availability: {e}")
            return []

calendar_service = CalendarService()
