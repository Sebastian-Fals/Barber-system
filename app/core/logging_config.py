import hashlib
import logging
import re
import sys
from logging.handlers import RotatingFileHandler

# Regex patterns for PII detection
_PHONE_RE = re.compile(r"\+?\d{7,15}")
_EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")


def sanitize_pii_for_log(message: str) -> str:
    """
    Sanitize PII (phone numbers, emails) from log messages.
    Phone numbers are hashed; emails are truncated to domain only.
    """
    if not message:
        return message

    # Replace emails: user@example.com → ***@example.com
    message = _EMAIL_RE.sub(lambda m: f"***@{m.group().split('@', 1)[-1]}", message)

    # Replace phone numbers: +573001234567 → [PHONE:sha256prefix]
    message = _PHONE_RE.sub(
        lambda m: f"[PHONE:{hashlib.sha256(m.group().encode()).hexdigest()[:8]}]",
        message,
    )

    return message


def setup_logging():
    # Create a custom logger
    logger = logging.getLogger("app")
    logger.setLevel(logging.INFO)

    # Create handlers
    c_handler = logging.StreamHandler(sys.stdout)
    f_handler = RotatingFileHandler("app.log", maxBytes=5 * 1024 * 1024, backupCount=2)

    c_handler.setLevel(logging.INFO)
    f_handler.setLevel(logging.INFO)

    # Create formatters and add it to handlers
    c_format = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    f_format = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")

    c_handler.setFormatter(c_format)
    f_handler.setFormatter(f_format)

    # Add handlers to the logger
    logger.addHandler(c_handler)
    logger.addHandler(f_handler)

    return logger


logger = setup_logging()
