"""
RED tests: Google credentials from environment variable.

Spec: secret-management — Google Credentials From Environment Variable.
- Valid JSON → from_service_account_info called
- Missing env var → service inits without crash, service is None
- Malformed JSON → JSONDecodeError raised
"""
import json
from unittest.mock import patch

import pytest

from app.core.config import settings
from app.features.calendar.service import CalendarService


class TestCalendarServiceCredentials:
    """Tests for Google credentials via GOOGLE_APPLICATION_CREDENTIALS_JSON (T1.5/T1.6)."""

    def test_valid_json_credentials_parsed_correctly(self):
        """
        Scenario: Valid JSON in environment variable.
        - GIVEN GOOGLE_APPLICATION_CREDENTIALS_JSON contains valid service account JSON
        - WHEN the calendar service initializes
        - THEN credentials are parsed from the env var and from_service_account_info is called.
        """
        creds_dict = {
            "type": "service_account",
            "project_id": "test-project",
            "private_key_id": "abc123",
            "private_key": "-----BEGIN PRIVATE KEY-----\nMOCK\n-----END PRIVATE KEY-----\n",
            "client_email": "test@test-project.iam.gserviceaccount.com",
            "client_id": "12345",
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
        }
        with patch.object(settings, "GOOGLE_APPLICATION_CREDENTIALS_JSON", json.dumps(creds_dict)):
            with patch("app.features.calendar.service.service_account") as mock_sa:
                with patch("app.features.calendar.service.build"):
                    CalendarService()
                    mock_sa.Credentials.from_service_account_info.assert_called_once()
                    call_args = mock_sa.Credentials.from_service_account_info.call_args
                    parsed = call_args[0][0]
                    assert parsed["type"] == "service_account"
                    assert parsed["client_email"] == "test@test-project.iam.gserviceaccount.com"

    def test_missing_env_var_service_none(self, monkeypatch):
        """
        Scenario: Missing environment variable.
        - GIVEN GOOGLE_APPLICATION_CREDENTIALS_JSON is not set
        - WHEN the calendar service initializes
        - THEN service inits without crash and self.service is None.
        """
        import app.core.config as config_mod

        monkeypatch.setattr(config_mod.settings, "GOOGLE_APPLICATION_CREDENTIALS_JSON", None)
        monkeypatch.setattr(config_mod.settings, "GOOGLE_APPLICATION_CREDENTIALS", "")

        svc = CalendarService()
        assert svc.service is None

    def test_malformed_json_raises_decode_error(self, monkeypatch):
        """
        Scenario: Invalid JSON in environment variable.
        - GIVEN GOOGLE_APPLICATION_CREDENTIALS_JSON contains malformed JSON
        - WHEN the calendar service initializes
        - THEN JSONDecodeError is raised.
        """
        import app.core.config as config_mod

        monkeypatch.setattr(config_mod.settings, "GOOGLE_APPLICATION_CREDENTIALS_JSON", "{not valid json")
        monkeypatch.setattr(config_mod.settings, "GOOGLE_APPLICATION_CREDENTIALS", "")

        with pytest.raises(json.JSONDecodeError):
            CalendarService()
