class AppError(Exception):
    """Base class for application exceptions."""

    pass


class BusinessCalendarError(AppError):
    """Errors related to business hours or calendar operations."""

    pass


class SlotOccupiedError(AppError):
    """The desired time slot is already taken."""

    pass


class ServiceValidationError(AppError):
    """Invalid input data (dates, times, ids)."""

    pass
