"""
Tests for Business model — Evolution API migration.

Spec: Business model replaces phone_number_id with instance_name
      and adds instance_apikey (EncryptedString).
"""

from app.models.models import Business


class TestBusinessEvolutionFields:
    """RED: Business model has instance_name and instance_apikey."""

    def test_instance_name_column_exists(self):
        """Business must have instance_name column (unique, indexed, not null)."""
        assert hasattr(Business, "instance_name"), "Business model must have instance_name attribute"
        col = getattr(Business, "instance_name")
        assert col.primary_key is False
        assert col.nullable is False
        # Should be unique and indexed
        assert col.unique is True
        assert col.index is True

    def test_instance_apikey_column_exists(self):
        """Business must have instance_apikey column (encrypted, not null)."""
        assert hasattr(Business, "instance_apikey"), "Business model must have instance_apikey attribute"
        col = getattr(Business, "instance_apikey")
        assert col.nullable is False

    def test_phone_number_id_removed(self):
        """phone_number_id must NOT exist on Business model."""
        assert not hasattr(Business, "phone_number_id"), "Business model must NOT have phone_number_id"

    def test_existing_columns_preserved(self):
        """Columns like id, name, phone, ai_enabled must still exist."""
        for col_name in ("id", "name", "phone", "calendar_id", "ai_enabled"):
            assert hasattr(Business, col_name), f"Business must retain existing column: {col_name}"
