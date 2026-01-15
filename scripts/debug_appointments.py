from app.core.database import SessionLocal
from app.models.models import Appointment, AppointmentStatus

db = SessionLocal()
appts = db.query(Appointment).filter(Appointment.status == AppointmentStatus.CONFIRMED).all()

print(f"Found {len(appts)} CONFIRMED appointments:")
for a in appts:
    print(f"ID: {a.id} | Date: {a.start_time} - {a.end_time} | Barber: {a.barber.name} | GCal ID: {a.google_event_id}")

db.close()
