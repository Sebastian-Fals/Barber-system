import os
import datetime
from sqlalchemy.orm import Session
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


    def watch_calendar(self, calendar_id: str, webhook_url: str, channel_id: str):
        """
        Subscribes to push notifications for a specific calendar.
        """
        if not self.service:
            print("Service not initialized")
            return None

        body = {
            "id": channel_id,
            "type": "web_hook",
            "address": webhook_url
        }
        
        try:
            print(f"Subscribing to {calendar_id} with channel {channel_id}")
            response = self.service.events().watch(calendarId=calendar_id, body=body).execute()
            print(f"Watch Response: {response}")
            return response
        except Exception as e:
            print(f"Error watching calendar {calendar_id}: {e}")
            return None

    def sync_events(self, calendar_id: str, db: Session = None):
        """
        Syncs events from Google Calendar to DB (Checking for cancellations).
        Ideally, we should store and use 'syncToken'. For MVP, we look back 24h.
        """
        if not self.service: return
        
        # We need a db session. Passing it as arg or creating new one?
        # Ideally caller handles DB session, or we create local if not provided.
        # But this service is usually instantiated globally. 
        # For the webhook handler, we will pass the DB session.
        if not db:
            print("Error: DB Session required for sync")
            return

        from app.models.models import Appointment, AppointmentStatus

        # Look back 24 hours to catch recent updates
        time_min = (datetime.datetime.utcnow() - datetime.timedelta(hours=24)).isoformat() + 'Z'
        
        try:
            print(f"Syncing events for {calendar_id} since {time_min}")
            events_result = self.service.events().list(
                calendarId=calendar_id,
                timeMin=time_min,
                singleEvents=True,
                showDeleted=True, # Important to catch cancellations
                orderBy='updated'
            ).execute()
            
            items = events_result.get('items', [])
            
            for event in items:
                g_id = event.get('id')
                status = event.get('status') # confirmed, tentative, cancelled
                
                if status == 'cancelled':
                    # Find appointment in DB
                    appt = db.query(Appointment).filter(
                        Appointment.google_event_id == g_id,
                        Appointment.status == AppointmentStatus.CONFIRMED
                    ).first()
                    
                    if appt:
                        print(f"Sync: Found cancelled event {g_id}. Cancelling local appointment {appt.id}")
                        appt.status = AppointmentStatus.CANCELLED
                        db.commit()
                        
                        # Notify Customer? (Optional: could be added here)
                        # whatsapp_service.send_message(..., "Tu cita fue cancelada...")
                        
        except Exception as e:
            print(f"Error syncing events: {e}")

calendar_service = CalendarService()
