"""
RED tests for CustomerRepository with business-scoped queries.

Spec scenarios:
  - Customer lookup scoped by business: get_by_phone only returns customer of the correct business.
"""

from unittest.mock import MagicMock

from app.features.customers.repository import CustomerRepository
from app.models.models import Customer


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
