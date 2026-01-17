import os
import sys

# Add app to path
sys.path.append(os.getcwd())

try:
    print("Importing modules...")
    from app.core.database import SessionLocal
    from app.services.booking_service import BookingService
    from app.services.conversation_service import ConversationService
    from app.services.flow_service import FlowManager

    print("Modules imported successfully.")

    db = SessionLocal()
    print("DB Session created.")

    booking = BookingService(db)
    print("BookingService instantiated.")

    flow = FlowManager(db)
    print("FlowManager instantiated.")

    # Mock phone ID
    conv = ConversationService(db, "123456789")
    print("ConversationService instantiated.")

    print("VERIFICATION SUCCESS: No import or syntax errors found.")

except Exception as e:
    print(f"VERIFICATION FAILED: {e}")
    import traceback

    traceback.print_exc()
finally:
    try:
        db.close()
    except:
        pass
