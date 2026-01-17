from datetime import datetime

import pytz

from app.core.config import settings


def get_local_timezone():
    """Returns the pytz timezone object configured in settings."""
    return pytz.timezone(settings.TIMEZONE)


def to_utc(dt):
    """
    Converts a datetime object to UTC.
    If naive, assumes it's already UTC (or raises warning?).
    Standardizing: If naive, assume Local (Colombia) then convert to UTC? No, usually expect Aware.
    """
    if isinstance(dt, str):
        try:
            # Try parsing ISO
            dt = datetime.fromisoformat(dt)
        except:
            pass

    if not isinstance(dt, datetime):
        return dt  # Cannot convert

    if dt.tzinfo is None:
        # If naive, localize to America/Bogota then convert to UTC?
        # Or assume UTC?
        # Safety: Assume America/Bogota (since app is standardized)
        tz = pytz.timezone(settings.TIMEZONE)
        dt = tz.localize(dt)

    return dt.astimezone(pytz.UTC)


def to_local(dt: datetime) -> datetime:
    """
    Converts a datetime to the configured local timezone.
    If dt is naive, assumes it is UTC (standard db storage).
    Returns a timezone-aware datetime in Local Time.
    """
    if dt.tzinfo is None:
        # Assume it's UTC if naive (e.g. read from simple DB)
        dt = pytz.UTC.localize(dt)

    return dt.astimezone(get_local_timezone())


def utcnow() -> datetime:
    """Returns current time in UTC (aware)."""
    return datetime.now(pytz.UTC)


def now_local() -> datetime:
    """Returns current time in Local Timezome (aware)."""
    return datetime.now(get_local_timezone())


def format_spanish_date(dt) -> str:
    """
    Formats a date/datetime to '17 de Enero'.
    Accepts date, datetime or ISO string.
    """
    if isinstance(dt, str):
        try:
            dt = datetime.fromisoformat(dt)
        except:
            return dt

    months = {
        1: "Enero",
        2: "Febrero",
        3: "Marzo",
        4: "Abril",
        5: "Mayo",
        6: "Junio",
        7: "Julio",
        8: "Agosto",
        9: "Septiembre",
        10: "Octubre",
        11: "Noviembre",
        12: "Diciembre",
    }

    # If it's a date object, it has checkable attributes, but safely accessing
    day = getattr(dt, "day", 0)
    month = getattr(dt, "month", 0)

    if day == 0:
        return str(dt)  # Fallback

    return f"{day} de {months.get(month, '')}"


def format_12h_time(t) -> str:
    """
    Formats a time object/string to '1:00 PM'.
    """
    if isinstance(t, str):
        # Try to parse HH:MM
        try:
            t = datetime.strptime(str(t).strip(), "%H:%M").time()
        except:
            return t

    if hasattr(t, "strftime"):
        return t.strftime("%I:%M %p")
    return str(t)
