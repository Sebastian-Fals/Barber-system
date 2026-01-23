import hashlib

from cryptography.fernet import Fernet

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
    """Decrypts a Fernet encrypted string."""
    if not value:
        return value
    if not _cipher_suite:
        raise ValueError("Encryption not configured (Missing ENCRYPTION_KEY)")

    try:
        decrypted_bytes = _cipher_suite.decrypt(value.encode("utf-8"))
        return decrypted_bytes.decode("utf-8")
    except Exception:
        # If decryption fails (wrong key, corrupted), return raw or raise?
        # Returning raw might expose ciphertext to UI but prevents crash.
        # For security, better to return Error or Empty.
        return "[Error: Decryption Failed]"


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
