import hashlib

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings

# Initialize Fernet with the key from settings
# Ensure ENCRYPTION_KEY is set in .env
try:
    _cipher_suite = Fernet(settings.ENCRYPTION_KEY) if settings.ENCRYPTION_KEY else None
except Exception as e:
    # If key is invalid, we might crash or just log. For safety, let's log.
    print(f"⚠️ Encryption Key Invalid or Missing: {e}")
    _cipher_suite = None


def encrypt(value: str) -> str:
    """Encrypts a string value using Fernet."""
    if not value:
        return value
    if not _cipher_suite:
        raise ValueError("Encryption not configured (Missing ENCRYPTION_KEY)")

    # Fernet expects bytes
    encrypted_bytes = _cipher_suite.encrypt(value.encode("utf-8"))
    return encrypted_bytes.decode("utf-8")


def decrypt(value: str) -> str:
    """Decrypts a Fernet encrypted string. Raises InvalidToken on failure."""
    if not value:
        return value
    if not _cipher_suite:
        raise ValueError("Encryption not configured (Missing ENCRYPTION_KEY)")

    decrypted_bytes = _cipher_suite.decrypt(value.encode("utf-8"))
    return decrypted_bytes.decode("utf-8")


def validate_encryption_key() -> None:
    """
    Validates the ENCRYPTION_KEY at startup by performing an encrypt/decrypt
    round-trip with a sentinel value. Raises ValueError if the key is missing,
    invalid, or produces incorrect results.

    Warning: Do NOT change ENCRYPTION_KEY after initial deployment.
    Changing it will make all encrypted data unreadable.
    """
    if not settings.ENCRYPTION_KEY:
        raise ValueError("ENCRYPTION_KEY is not set. Encryption not configured.")
    if not _cipher_suite:
        raise ValueError("ENCRYPTION_KEY is invalid or could not initialize Fernet.")

    sentinel = "__KEY_CHECK__"
    try:
        encrypted = encrypt(sentinel)
        decrypted = decrypt(encrypted)
    except InvalidToken:
        raise ValueError(
            "ENCRYPTION_KEY validation FAILED. "
            "Key mismatch — all encrypted data is unreadable. "
            "Do NOT change ENCRYPTION_KEY after initial deployment."
        )
    except Exception as e:
        raise ValueError(f"ENCRYPTION_KEY validation error: {e}")

    if decrypted != sentinel:
        raise ValueError("ENCRYPTION_KEY validation FAILED. " "Key mismatch — round-trip encryption check failed.")


def hash_value(value: str) -> str:
    """
    Creates a SHA-256 hash of the value.
    Used for 'Blind Index' searching (e.g. searching by phone number).
    """
    if not value:
        return value
    # We can add a "pepper" from config if we want extra security against rainbow tables
    # but for now, simple SHA256 is enough for this context.
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
