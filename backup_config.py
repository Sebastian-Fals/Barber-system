from app.core.database import SessionLocal
from app.models.models import Business, Barber

db = SessionLocal()
b = db.query(Business).first()
if b:
    print(f"PHONE_ID={b.phone_number_id}")
    print(f"NAME={b.name}")
    print(f"CAL_ID={b.calendar_id}")
else:
    print("No business found")

barbers = db.query(Barber).all()
for bar in barbers:
     print(f"BARBER: {bar.name} | CAL: {bar.calendar_id}")
