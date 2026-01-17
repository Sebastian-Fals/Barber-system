from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.models import Barber, Business

db = SessionLocal()
print("--- Businesses ---")
for b in db.query(Business).all():
    print(f"ID: {b.id} | Name: {b.name} | CalID: {b.calendar_id}")

print("\n--- Barbers ---")
for b in db.query(Barber).all():
    print(f"ID: {b.id} | Name: {b.name} | CalID: {b.calendar_id} | BusinessID: {b.business_id}")

db.close()
