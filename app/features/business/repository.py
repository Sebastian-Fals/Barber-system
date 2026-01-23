from typing import Optional

from sqlalchemy.orm import Session

from app.models.models import Business
from app.repositories.base import BaseRepository


class BusinessRepository(BaseRepository[Business]):
    def __init__(self, db: Session):
        super().__init__(Business, db)

    # Add specific business queries if needed
    def get_by_phone_number_id(self, phone_number_id: str) -> Optional[Business]:
        return self.db.query(self.model).filter(self.model.phone_number_id == phone_number_id).first()
