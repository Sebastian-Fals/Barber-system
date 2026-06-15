"""
RED tests: Encryption key validation at startup + silent fail removal.

Spec: encryption-validation — Startup Encryption Key Validation.
- validate_encryption_key() with valid key → no exception
- Invalid key → ValueError
- Missing key → ValueError
- decrypt() with corrupted ciphertext → InvalidToken (not silent fallback)
"""
import pytest
from cryptography.fernet import Fernet, InvalidToken

from app.core.security import decrypt, validate_encryption_key


class TestValidateEncryptionKey:
    """Tests for startup encryption key validation (T1.3)."""

    def test_valid_key_does_not_raise(self, monkeypatch):
        """
        Scenario: Valid encryption key.
        - GIVEN ENCRYPTION_KEY is a valid Fernet key
        - WHEN validate_encryption_key() is called
        - THEN no exception is raised.
        """
        valid_key = Fernet.generate_key().decode()
        monkeypatch.setattr("app.core.security.settings.ENCRYPTION_KEY", valid_key)
        # Re-init the cipher suite with the new key
        import app.core.security as sec

        sec._cipher_suite = Fernet(valid_key)

        # Should not raise
        validate_encryption_key()

    def test_invalid_key_raises_value_error(self, monkeypatch):
        """
        Scenario: Invalid or corrupted encryption key.
        - GIVEN ENCRYPTION_KEY is invalid
        - WHEN validate_encryption_key() is called
        - THEN ValueError is raised.
        """
        # Set an invalid key that Fernet cannot parse
        monkeypatch.setattr("app.core.security.settings.ENCRYPTION_KEY", "not-a-valid-key-!!!!")
        import app.core.security as sec

        # Force re-init with the invalid key — Fernet will be None
        sec._cipher_suite = None

        with pytest.raises(ValueError, match="invalid|could not initialize"):
            validate_encryption_key()

    def test_missing_key_raises_value_error(self, monkeypatch):
        """
        Scenario: Missing encryption key.
        - GIVEN ENCRYPTION_KEY is None
        - WHEN validate_encryption_key() is called
        - THEN ValueError is raised.
        """
        monkeypatch.setattr("app.core.security.settings.ENCRYPTION_KEY", None)
        import app.core.security as sec

        sec._cipher_suite = None

        with pytest.raises(ValueError):
            validate_encryption_key()


class TestDecryptNoSilentFail:
    """Tests for removal of silent [Error: Decryption Failed] fallback (T1.4)."""

    def test_decrypt_raises_instead_of_silent_fail(self):
        """
        - GIVEN a corrupted ciphertext (not valid Fernet)
        - WHEN decrypt() is called
        - THEN InvalidToken is raised (NOT silent "[Error: Decryption Failed]").
        """
        valid_key = Fernet.generate_key().decode()
        import app.core.security as sec

        sec._cipher_suite = Fernet(valid_key)

        with pytest.raises(InvalidToken):
            decrypt("this-is-not-valid-ciphertext")

    def test_decrypt_with_wrong_key_raises_invalid_token(self):
        """
        - GIVEN ciphertext encrypted with key A
        - WHEN decrypt() is called with key B
        - THEN InvalidToken is raised.
        """
        key_a = Fernet.generate_key()
        key_b = Fernet.generate_key()
        cipher_a = Fernet(key_a)

        # Encrypt with key A
        ciphertext = cipher_a.encrypt(b"test-data").decode()

        # Set cipher suite to key B
        import app.core.security as sec

        sec._cipher_suite = Fernet(key_b)

        with pytest.raises(InvalidToken):
            decrypt(ciphertext)
