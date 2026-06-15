"""
Tests for BusinessRepository.get_by_phone_number_id (existing method, multi-tenant context).

Spec scenario:
  - get_by_phone_number_id returns Business or None.
"""

from unittest.mock import MagicMock

from app.features.business.repository import BusinessRepository
from app.models.models import Business


class TestBusinessRepository:
    """BusinessRepository.get_by_phone_number_id resolves business by phone_number_id."""

    def test_get_by_phone_number_id_returns_business(self):
        """When phone_number_id matches, return the business."""
        db = MagicMock()
        business = Business(id=1, name="Test Biz", phone_number_id="123456")

        mock_query = db.query.return_value
        mock_query.filter.return_value.first.return_value = business

        repo = BusinessRepository(db)
        result = repo.get_by_phone_number_id("123456")

        assert result is not None
        assert result.id == 1
        assert result.phone_number_id == "123456"

    def test_get_by_phone_number_id_returns_none_for_unknown(self):
        """When phone_number_id does not match, return None."""
        db = MagicMock()

        mock_query = db.query.return_value
        mock_query.filter.return_value.first.return_value = None

        repo = BusinessRepository(db)
        result = repo.get_by_phone_number_id("999999")

        assert result is None
