from typing import Optional

from sqlalchemy.orm import Session

from app.models.models import Business
from app.repositories.base import BaseRepository


class BusinessRepository(BaseRepository[Business]):
    def __init__(self, db: Session):
        super().__init__(Business, db)

    # Add specific business queries if needed
    def get_by_instance_name(self, instance_name: str) -> Optional[Business]:
        return self.db.query(self.model).filter(self.model.instance_name == instance_name).first()
