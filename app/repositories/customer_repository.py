from typing import Optional

from sqlalchemy.orm import Session

from app.models.models import Customer
from app.repositories.base import BaseRepository


class CustomerRepository(BaseRepository[Customer]):
    def __init__(self, db: Session):
        super().__init__(Customer, db)

    def get_by_phone(self, phone: str) -> Optional[Customer]:
        return self.db.query(self.model).filter(self.model.phone == phone).first()

    def update_state(self, customer: Customer, new_state: str) -> Customer:
        customer.conversation_state = new_state
        self.db.add(customer)
        self.db.commit()
        self.db.refresh(customer)
        return customer

    def update_data(self, customer: Customer, data: str) -> Customer:
        customer.conversation_data = data
        self.db.add(customer)
        self.db.commit()
        self.db.refresh(customer)
        return customer
