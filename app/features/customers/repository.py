from typing import Optional

from sqlalchemy.orm import Session

from app.core.security import hash_value
from app.models.models import Customer
from app.repositories.base import BaseRepository


class CustomerRepository(BaseRepository[Customer]):
    def __init__(self, db: Session):
        super().__init__(Customer, db)

    def get_by_phone(self, phone: str, business_id: int) -> Optional[Customer]:
        return (
            self.db.query(self.model)
            .filter(
                self.model.phone_hash == hash_value(phone),
                self.model.business_id == business_id,
            )
            .first()
        )

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

    def update(self, db_obj: Customer, obj_in: dict) -> Customer:
        # Debug Override
        from app.core.logging_config import logger

        logger.info(f"AUDIT: Updating Customer {db_obj.phone_hash} with {obj_in}")

        updated = super().update(db_obj, obj_in)
        logger.info(f"AUDIT: Committed. New Name in DB: {updated.name}")
        return updated
