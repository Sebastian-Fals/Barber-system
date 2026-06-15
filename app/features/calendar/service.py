import datetime
import os
import threading

import pytz
from google.oauth2 import service_account
from googleapiclient.discovery import build
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.config import settings


class CalendarService:
    SCOPES = ["https://www.googleapis.com/auth/calendar"]

    def __init__(self):
        self.creds = None
        self.service = None
        self.lock = threading.Lock()
        self._authenticate()

    def _authenticate(self):
        if settings.GOOGLE_APPLICATION_CREDENTIALS_JSON:
            import json

            try:
                creds_dict = json.loads(settings.GOOGLE_APPLICATION_CREDENTIALS_JSON)
                self.creds = service_account.Credentials.from_service_account_info(creds_dict, scopes=self.SCOPES)
                self.service = build("calendar", "v3", credentials=self.creds)
            except json.JSONDecodeError as e:
                print(f"FATAL: GOOGLE_APPLICATION_CREDENTIALS_JSON is not valid JSON: {e}")
                raise
        elif os.path.exists(settings.GOOGLE_APPLICATION_CREDENTIALS):
            self.creds = service_account.Credentials.from_service_account_file(
                settings.GOOGLE_APPLICATION_CREDENTIALS, scopes=self.SCOPES
            )
            self.service = build("calendar", "v3", credentials=self.creds)
        else:
            print("Warning: GOOGLE_APPLICATION_CREDENTIALS_JSON not set. Calendar disabled.")

    def create_event(
        self,
        calendar_id: str,
        summary: str,
        start_time: datetime.datetime,
        end_time: datetime.datetime,
        description: str = "",
        attendees: list = None,
    ):
        """
        Creates an event in the specified calendar.
        """
        if not self.service:
            return None

        event = {
            "summary": summary,
            "description": description,
            "start": {
                "dateTime": start_time.isoformat(),
                "timeZone": settings.TIMEZONE,
            },
            "end": {
                "dateTime": end_time.isoformat(),
                "timeZone": settings.TIMEZONE,
            },
        }

        if attendees:
            # attendees expects [{'email': 'foo@bar.com'}]
            event["attendees"] = [{"email": email} for email in attendees]

        try:
            with self.lock:
                event = self.service.events().insert(calendarId=calendar_id, body=event).execute()
            print(f"Event created: {event.get('htmlLink')}")
            return event.get("id")
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
            # Ensure filtering respects the configured timezone
            tz = pytz.timezone(settings.TIMEZONE)

            # If naive, assume local/target timezone
            if start_time.tzinfo is None:
                start_time = tz.localize(start_time)
            if end_time.tzinfo is None:
                end_time = tz.localize(end_time)

            print(f"Checking gcal for {calendar_id} from {start_time} to {end_time}")
            with self.lock:
                events_result = (
                    self.service.events()
                    .list(
                        calendarId=calendar_id,
                        timeMin=start_time.isoformat(),
                        timeMax=end_time.isoformat(),
                        singleEvents=True,
                        orderBy="startTime",
                    )
                    .execute()
                )

            items = events_result.get("items", [])
            busy_slots = []

            for event in items:
                # Handle 'date' (all day) vs 'dateTime'
                start = event["start"].get("dateTime", event["start"].get("date"))
                end = event["end"].get("dateTime", event["end"].get("date"))

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

        body = {"id": channel_id, "type": "web_hook", "address": webhook_url}

        try:
            print(f"Subscribing to {calendar_id} with channel {channel_id}")
            response = self.service.events().watch(calendarId=calendar_id, body=body).execute()
            print(f"Watch Response: {response}")
            return response
        except Exception as e:
            print(f"Error watching calendar {calendar_id}: {e}")
            return None

    def delete_event(self, calendar_id: str, event_id: str):
        """
        Deletes an event from the specified calendar.
        """
        if not self.service:
            return False

        try:
            with self.lock:
                self.service.events().delete(calendarId=calendar_id, eventId=event_id).execute()
            print(f"Event deleted: {event_id} from {calendar_id}")
            return True
        except Exception as e:
            print(f"Error deleting event {event_id}: {e}")
            return False

    def sync_events(self, calendar_id: str, db: Session = None):
        """
        Syncs events from Google Calendar to DB (Checking for cancellations).
        Ideally, we should store and use 'syncToken'. For MVP, we look back 24h.
        """
        if not self.service:
            return

        # We need a db session. Passing it as arg or creating new one?
        # Ideally caller handles DB session, or we create local if not provided.
        # But this service is usually instantiated globally.
        # For the webhook handler, we will pass the DB session.
        # If no DB session provided, verify if we can create one
        should_close_db = False
        if not db:
            from app.core.database import SessionLocal

            db = SessionLocal()
            should_close_db = True

        from app.models.models import Appointment, AppointmentStatus

        # Look back 24 hours (Local Time Aware)
        tz = pytz.timezone(settings.TIMEZONE)
        now = datetime.datetime.now(tz)
        time_min = (now - datetime.timedelta(hours=24)).isoformat()

        try:
            print(f"Syncing events for {calendar_id} since {time_min}")
            with self.lock:
                events_result = (
                    self.service.events()
                    .list(
                        calendarId=calendar_id,
                        timeMin=time_min,
                        singleEvents=True,
                        showDeleted=True,  # Important to catch cancellations
                        orderBy="updated",
                    )
                    .execute()
                )

            items = events_result.get("items", [])
            print(f"Sync: Found {len(items)} events modified in the last 24h")

            cancelled_ids = []
            for event in items:
                g_id = event.get("id")
                status = event.get("status")  # confirmed, tentative, cancelled

                if status == "cancelled" and g_id:
                    cancelled_ids.append(g_id)

            if cancelled_ids:
                # Bulk Update
                # Fetch appointments that exist and are confirmed
                appts_to_cancel = (
                    db.query(Appointment)
                    .filter(
                        or_(
                            Appointment.google_barber_event_id.in_(cancelled_ids),
                            Appointment.google_business_event_id.in_(cancelled_ids),
                        ),
                        Appointment.status == AppointmentStatus.CONFIRMED,
                    )
                    .all()
                )

                if appts_to_cancel:
                    print(f"Sync: Bulk Cancelling {len(appts_to_cancel)} appointments")
                    for appt in appts_to_cancel:
                        appt.status = AppointmentStatus.CANCELLED
                        print(f" - Cancelled Appt ID {appt.id}")
                    db.commit()
                else:
                    print("Sync: No matching local appointments to cancel.")
            else:
                print("Sync: No cancelled events found.")

        except Exception as e:
            print(f"Error syncing events: {e}")
        finally:
            if should_close_db:
                db.close()


calendar_service = CalendarService()
