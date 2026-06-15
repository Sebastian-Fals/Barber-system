"""
RED tests: PII sanitization in logs.

Spec: secret-management (logging) — sanitize phone numbers and emails in log output.
"""
from app.core.logging_config import sanitize_pii_for_log


class TestPiiSanitization:
    """Tests for PII sanitization in log messages (T1.7)."""

    def test_phone_number_is_hashed(self):
        """
        - GIVEN a message containing a phone number like "+573001234567"
        - WHEN sanitize_pii_for_log() is called
        - THEN the phone number is replaced with a hashed/truncated version.
        """
        msg = "User +573001234567 booked appointment"
        sanitized = sanitize_pii_for_log(msg)

        assert "+573001234567" not in sanitized, f"Phone number should be sanitized, got: {sanitized}"
        assert "booked appointment" in sanitized, "Non-PII content should be preserved"

    def test_email_is_truncated(self):
        """
        - GIVEN a message containing an email like "user@example.com"
        - WHEN sanitize_pii_for_log() is called
        - THEN the email is truncated/hashed.
        """
        msg = "Contact user@example.com for details"
        sanitized = sanitize_pii_for_log(msg)

        assert "user@example.com" not in sanitized, f"Email should be sanitized, got: {sanitized}"
        assert "for details" in sanitized, "Non-PII content should be preserved"

    def test_message_without_pii_passes_through(self):
        """
        - GIVEN a message with no PII
        - WHEN sanitize_pii_for_log() is called
        - THEN the message is unchanged.
        """
        msg = "Appointment created successfully"
        sanitized = sanitize_pii_for_log(msg)

        assert sanitized == msg, f"Message without PII should be unchanged, got: {sanitized}"

    def test_multiple_phones_and_emails_sanitized(self):
        """
        - GIVEN a message with multiple phone numbers and emails
        - WHEN sanitize_pii_for_log() is called
        - THEN all PII is sanitized.
        """
        msg = "Phones: +57000111, +57000222. Emails: a@b.com, c@d.co"
        sanitized = sanitize_pii_for_log(msg)

        assert "+57000111" not in sanitized
        assert "+57000222" not in sanitized
        assert "a@b.com" not in sanitized
        assert "c@d.co" not in sanitized
        assert "Phones:" in sanitized
        assert "Emails:" in sanitized
