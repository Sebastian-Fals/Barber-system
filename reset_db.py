from app.core.database import SessionLocal, engine, Base
from app.models.models import Business, Barber, Customer, Appointment
import sys

# 1. Drop and Create
print("🗑️ Dropping all tables...")
Base.metadata.drop_all(bind=engine)
print("✨ Creating all tables...")
Base.metadata.create_all(bind=engine)

# 2. Seed Data
db = SessionLocal()

# Business
print("🌱 Seeding Business...")
business = Business(
    name="PeluqueriaSebastian",
    phone_number_id="86196104034",
    calendar_id="sebastian.fals.lopez@gmail.com",
    ai_enabled=True,
    schedule='{"0": {"start": 9, "end": 18}, "1": {"start": 9, "end": 18}, "2": {"start": 9, "end": 18}, "3": {"start": 9, "end": 18}, "4": {"start": 9, "end": 18}, "5": {"start": 9, "end": 18}}'
)
db.add(business)
db.commit()
db.refresh(business)

# Barber
print("🌱 Seeding Barber Alejandro...")
barber = Barber(
    name="Alejandro",
    phone="3001234567",
    calendar_id="c14c89385ecab9b221f1b173c33cba7dfcfce2eb1f8ba91ff31d69b24822d3b0@group.calendar.google.com",
    business_id=business.id
)
db.add(barber)
db.commit()

print("✅ Database reset complete!")
db.close()
