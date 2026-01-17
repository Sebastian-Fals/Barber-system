import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.i18n import message_loader

print("Testing i18n Service...")
try:
    # Test simple key
    msg = message_loader.get("menu_book")
    assert msg == "📅 Agendar Cita", f"Expected '📅 Agendar Cita', got '{msg}'"
    print("  Simple Key: OK")

    # Test formatted key
    msg_formatted = message_loader.get("welcome_new_user", business_name="BarberShop")
    assert "BarberShop" in msg_formatted, "Formatting failed"
    print("  Formatted Key: OK")

    # Test missing key (fallback)
    msg_missing = message_loader.get("non_existent_key")
    assert msg_missing == "non_existent_key", "Fallback failed"
    print("  Missing Key Fallback: OK")

    print("i18n Service Verification PASSED")
except Exception as e:
    print(f"FAILED: {e}")
    sys.exit(1)
