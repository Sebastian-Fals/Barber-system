from sqlalchemy.orm import Session

from app.models.models import Barber
from app.repositories.base import BaseRepository


class BarberRepository(BaseRepository[Barber]):
    def __init__(self, db: Session):
        super().__init__(Barber, db)

    def get_by_business(self, business_id: int) -> list[Barber]:
        return self.db.query(self.model).filter(self.model.business_id == business_id).all()
