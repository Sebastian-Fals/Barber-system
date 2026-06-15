from sqlalchemy.orm import Session

from app.models.models import Service
from app.repositories.base import BaseRepository


class ServiceRepository(BaseRepository[Service]):
    def __init__(self, db: Session):
        super().__init__(Service, db)

    def get_by_business(self, business_id: int) -> list[Service]:
        return self.db.query(self.model).filter(self.model.business_id == business_id).all()
