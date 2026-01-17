import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

print("Step 1: Import SessionLocal")
try:
    from app.core.database import SessionLocal

    print("OK")
except Exception as e:
    print(f"FAIL: {e}")
    sys.exit(1)

print("Step 2: Import CustomerRepository")
try:
    from app.repositories.customer_repository import CustomerRepository

    print("OK")
except Exception as e:
    print(f"FAIL: {e}")
    sys.exit(1)

print("Step 3: Import AppointmentRepository")
try:
    from app.repositories.appointment_repository import AppointmentRepository

    print("OK")
except Exception as e:
    print(f"FAIL: {e}")
    sys.exit(1)

print("Step 4: Import BarberRepository")
try:
    from app.repositories.barber_repository import BarberRepository

    print("OK")
except Exception as e:
    print(f"FAIL: {e}")
    sys.exit(1)

print("Step 5: Import BusinessRepository")
try:
    from app.repositories.business_repository import BusinessRepository

    print("OK")
except Exception as e:
    print(f"FAIL: {e}")
    sys.exit(1)

print("Step 6: Import Models")
try:
    from app.models.models import AppointmentStatus, CustomerData

    print("OK")
except Exception as e:
    print(f"FAIL: {e}")
    sys.exit(1)

print("All Imports Passed")
