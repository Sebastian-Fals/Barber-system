from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.models import Appointment, AppointmentStatus
from app.repositories.base import BaseRepository


class AppointmentRepository(BaseRepository[Appointment]):
    def __init__(self, db: Session):
        super().__init__(Appointment, db)

    def get_overlapping_confirmed(
        self, barber_id: int, start_time: datetime, end_time: datetime
    ) -> Optional[Appointment]:
        """
        Checks for any CONFIRMED appointment that overlaps with the given range.
        Input params should be timezone-aware (UTC preferably).
        """
        return (
            self.db.query(self.model)
            .filter(
                self.model.barber_id == barber_id,
                self.model.status == AppointmentStatus.CONFIRMED,
                self.model.start_time < end_time,
                self.model.end_time > start_time,
            )
            .first()
        )

    def get_by_barber_and_date_range(self, barber_id: int, start: datetime, end: datetime) -> List[Appointment]:
        return (
            self.db.query(self.model)
            .filter(
                self.model.barber_id == barber_id,
                self.model.start_time >= start,
                self.model.start_time < end,
                self.model.status != AppointmentStatus.CANCELLED,
            )
            .all()
        )

    def get_active_for_customer(self, customer_id: int) -> List[Appointment]:
        """
        Returns confirmed appointments in the future for a specific customer.
        """
        return (
            self.db.query(self.model)
            .filter(
                self.model.customer_id == customer_id,
                self.model.status == AppointmentStatus.CONFIRMED.value,
                self.model.start_time > datetime.now(timezone.utc),
            )
            .order_by(self.model.start_time.asc())
            .all()
        )
