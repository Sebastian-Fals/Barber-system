import json

from sqlalchemy.orm import Session

from app.models.models import Customer


class FlowManager:
    def __init__(self, db: Session):
        self.db = db

    def get_state(self, customer: Customer):
        return customer.conversation_state

    def update_state(self, customer: Customer, new_state: str, data: dict = None):
        customer.conversation_state = new_state
        if data is not None:
            # Ensure we don't accidentally nest JSON strings
            if isinstance(data, str):
                try:
                    data = json.loads(data)
                except (ValueError, TypeError):
                    pass
            customer.conversation_data = json.dumps(data)
        self.db.commit()

    def get_data(self, customer: Customer) -> dict:
        try:
            return json.loads(customer.conversation_data)
        except (ValueError, TypeError):
            return {}

    def update_data(self, customer: Customer, key: str, value):
        data = self.get_data(customer)
        data[key] = value
        customer.conversation_data = json.dumps(data)
        self.db.commit()
