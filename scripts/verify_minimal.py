import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

print("Step 1: Imports")
try:
    from app.core.database import SessionLocal

    print("  Import SessionLocal: OK")
    from app.repositories.customer_repository import CustomerRepository

    print("  Import CustomerRepository: OK")
except Exception as e:
    print(f"  Import Failed: {e}")
    sys.exit(1)

print("Step 2: DB Connection")
try:
    db = SessionLocal()
    print("  Session Created: OK")
    db.close()
except Exception as e:
    print(f"  DB Connection Failed: {e}")
    sys.exit(1)

print("Minimal Test Passed")
