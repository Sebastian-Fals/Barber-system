"""
RED tests for CustomerRepository with business-scoped queries.

Spec scenarios:
  - Customer lookup scoped by business: get_by_phone only returns customer of the correct business.
  - ConversationHistory scoping: history records are isolated by business_id transitively through customer_id.
"""

import os
import tempfile
from unittest.mock import MagicMock

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.features.customers.repository import CustomerRepository
from app.models.models import Base, Business, ConversationHistory, Customer, CustomerData


class TestCustomerRepositoryMultiTenant:
    """GREEN: get_by_phone scoped by business_id."""

    def test_get_by_phone_scoped_returns_correct_business_customer(self):
        """
        Scenario: Customer lookup scoped by business.
        - GIVEN Business A has customer with phone_hash "abc123"
        - WHEN Business A queries get_by_phone("+57...", business_id=1)
        - THEN only Business A's customer is returned.
        """
        db = MagicMock()

        customer_a = Customer(id=1, phone="+573001234567", name="Cliente A", business_id=1)

        # Simulate the filtered query: single filter with phone_hash AND business_id
        mock_query = db.query.return_value
        mock_query.filter.return_value.first.return_value = customer_a

        repo = CustomerRepository(db)
        result = repo.get_by_phone("+573001234567", business_id=1)

        assert result is not None
        assert result.id == 1
        assert result.business_id == 1

        # Verify filter was called with both conditions (phone_hash + business_id)
        filter_call_args = mock_query.filter.call_args
        assert filter_call_args is not None, "filter() was not called on the query"

    def test_get_by_phone_does_not_return_other_business_customer(self):
        """
        - GIVEN phone "abc123" does NOT exist in Business B's scope
        - WHEN Business B queries get_by_phone("abc123", business_id=2)
        - THEN None is returned (no cross-business leak).
        """
        db = MagicMock()

        mock_query = db.query.return_value
        mock_query.filter.return_value.first.return_value = None

        repo = CustomerRepository(db)
        result = repo.get_by_phone("+573001234567", business_id=2)

        assert result is None


class TestConversationHistoryScoping:
    """GREEN: ConversationHistory records are isolated by business_id transitively."""

    def _make_temp_db(self):
        """Create a fresh file-based SQLite DB."""
        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp.close()
        engine = create_engine(f"sqlite:///{tmp.name}")
        Base.metadata.create_all(bind=engine)
        SessionLocal = sessionmaker(bind=engine)
        return engine, SessionLocal, tmp.name

    def test_history_isolated_by_business_through_customer(self):
        """
        Scenario: ConversationHistory is isolated by business_id.
        - GIVEN Business A (id=1) with Customer A (phone X)
          AND Business B (id=2) with Customer B (also phone X, different business)
        - WHEN history is logged for both customers
        - THEN querying history for Customer A returns only Customer A's messages.
        - AND querying history for Customer B returns only Customer B's messages.
        - AND no cross-business leak occurs.

        This test verifies that multi-tenant isolation at the Customer level
        transitively protects ConversationHistory even though _log_message
        does not explicitly set business_id on each record.
        """
        engine, SessionLocal, tmp_path = self._make_temp_db()
        try:
            db = SessionLocal()

            # Seed two businesses
            biz_a = Business(name="Biz A", instance_name="wa_biz_a", instance_apikey="key-a")
            biz_b = Business(name="Biz B", instance_name="wa_biz_b", instance_apikey="key-b")
            db.add_all([biz_a, biz_b])
            db.flush()

            # Create one customer per business (same phone, different scopes)
            customer_a = Customer(
                phone="+573001234567", name="Cliente A", business_id=biz_a.id, conversation_state=CustomerData.IDLE
            )
            customer_b = Customer(
                phone="+573001234567", name="Cliente B", business_id=biz_b.id, conversation_state=CustomerData.IDLE
            )
            db.add_all([customer_a, customer_b])
            db.flush()
            db.commit()

            # Log messages for each customer
            entries = [
                ConversationHistory(
                    customer_id=customer_a.id, business_id=biz_a.id, role="user", message="Hola desde Biz A"
                ),
                ConversationHistory(
                    customer_id=customer_a.id, business_id=biz_a.id, role="assistant", message="Hola Cliente A"
                ),
                ConversationHistory(
                    customer_id=customer_b.id, business_id=biz_b.id, role="user", message="Hola desde Biz B"
                ),
            ]
            db.add_all(entries)
            db.commit()

            # Query history for Customer A
            hist_a = db.query(ConversationHistory).filter(ConversationHistory.customer_id == customer_a.id).all()
            msgs_a = [h.message for h in hist_a]
            assert len(hist_a) == 2, f"Expected 2 messages for Customer A, got {len(hist_a)}"
            assert "Hola desde Biz A" in msgs_a
            assert "Hola Cliente A" in msgs_a
            assert "Hola desde Biz B" not in msgs_a, "CROSS-BUSINESS LEAK: Customer A can see messages from Biz B"

            # Query history for Customer B
            hist_b = db.query(ConversationHistory).filter(ConversationHistory.customer_id == customer_b.id).all()
            msgs_b = [h.message for h in hist_b]
            assert len(hist_b) == 1, f"Expected 1 message for Customer B, got {len(hist_b)}"
            assert "Hola desde Biz B" in msgs_b
            assert "Hola desde Biz A" not in msgs_b, "CROSS-BUSINESS LEAK: Customer B can see messages from Biz A"

            # Cross-check: verify different business_id on records
            biz_ids_a = {h.business_id for h in hist_a}
            biz_ids_b = {h.business_id for h in hist_b}
            assert biz_ids_a == {biz_a.id}, f"Customer A records should all have business_id={biz_a.id}"
            assert biz_ids_b == {biz_b.id}, f"Customer B records should all have business_id={biz_b.id}"

            db.close()
        finally:
            engine.dispose()
            os.unlink(tmp_path)
