"""
Tests for app configuration — Evolution API migration.

Spec: config.py removes WHATSAPP_API_TOKEN/WHATSAPP_VERIFY_TOKEN,
      adds EVOLUTION_API_URL.
"""

import os


class TestEvolutionConfig:
    """Ensure Evolution settings replace Meta WhatsApp settings."""

    def test_evolution_api_url_exists(self):
        """Settings must have EVOLUTION_API_URL."""
        from app.core.config import Settings

        # Verify EVOLUTION_API_URL is a declared field
        fields = Settings.model_fields
        assert "EVOLUTION_API_URL" in fields, "EVOLUTION_API_URL missing from Settings"

    def test_meta_whatsapp_settings_removed(self):
        """WHATSAPP_API_TOKEN and WHATSAPP_VERIFY_TOKEN must NOT exist."""
        from app.core.config import Settings

        fields = Settings.model_fields
        assert "WHATSAPP_API_TOKEN" not in fields, "WHATSAPP_API_TOKEN must be removed"
        assert "WHATSAPP_VERIFY_TOKEN" not in fields, "WHATSAPP_VERIFY_TOKEN must be removed"

    def test_evolution_api_url_has_correct_type(self):
        """EVOLUTION_API_URL must be of type str."""
        from app.core.config import Settings

        fields = Settings.model_fields
        field = fields["EVOLUTION_API_URL"]
        # Pydantic v2 stores annotation in annotation attribute
        assert field.annotation == str, f"EVOLUTION_API_URL must be str, got {field.annotation}"

    def test_project_name_preserved(self):
        """PROJECT_NAME must still exist."""
        from app.core.config import Settings

        fields = Settings.model_fields
        assert "PROJECT_NAME" in fields
