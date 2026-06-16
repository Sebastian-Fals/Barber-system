"""
Tests for BusinessRepository.get_by_instance_name (Evolution migration).

Spec scenario:
  - get_by_instance_name returns Business or None.
"""

from unittest.mock import MagicMock

from app.features.business.repository import BusinessRepository
from app.models.models import Business


class TestBusinessRepository:
    """BusinessRepository.get_by_instance_name resolves business by instance_name."""

    def test_get_by_instance_name_returns_business(self):
        """When instance_name matches, return the business."""
        db = MagicMock()
        business = Business(id=1, name="Test Biz")
        business.instance_name = "barberia-latino"
        business.instance_apikey = "api-key-123"

        mock_query = db.query.return_value
        mock_query.filter.return_value.first.return_value = business

        repo = BusinessRepository(db)
        result = repo.get_by_instance_name("barberia-latino")

        assert result is not None
        assert result.id == 1
        assert result.instance_name == "barberia-latino"

    def test_get_by_instance_name_returns_none_for_unknown(self):
        """When instance_name does not match, return None."""
        db = MagicMock()

        mock_query = db.query.return_value
        mock_query.filter.return_value.first.return_value = None

        repo = BusinessRepository(db)
        result = repo.get_by_instance_name("unknown-instance")

        assert result is None

    def test_get_by_phone_number_id_removed(self):
        """get_by_phone_number_id must NOT exist."""
        repo = BusinessRepository.__new__(BusinessRepository)
        assert not hasattr(repo, "get_by_phone_number_id"), "get_by_phone_number_id must be removed"
        assert hasattr(repo, "get_by_instance_name"), "get_by_instance_name must exist"
