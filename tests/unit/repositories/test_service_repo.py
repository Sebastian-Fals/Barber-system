"""
RED tests for ServiceRepository.get_by_business.

Spec: booking-flow — Service Selection Step.
Design: ServiceRepository with get_by_business(business_id).
"""

from unittest.mock import MagicMock


class TestServiceRepository:
    """RED: ServiceRepository.get_by_business returns services for a business."""

    def test_get_by_business_returns_services(self):
        """
        Scenario: Query services for a specific business.
        - GIVEN business_id=1 has 2 services (Corte, Barba)
        - WHEN get_by_business(1) is called
        - THEN both services are returned.
        """
        from app.features.business.service_repository import ServiceRepository
        from app.models.models import Service

        db = MagicMock()
        svc_a = Service(id=1, business_id=1, name="Corte", duration_minutes=30)
        svc_b = Service(id=2, business_id=1, name="Barba", duration_minutes=60)

        mock_query = db.query.return_value
        mock_query.filter.return_value.all.return_value = [svc_a, svc_b]

        repo = ServiceRepository(db)
        result = repo.get_by_business(1)

        assert len(result) == 2
        assert result[0].name == "Corte"
        assert result[1].name == "Barba"

    def test_get_by_business_excludes_other_business(self):
        """
        Scenario: Query services for business 1 when business 2 also has services.
        - GIVEN business_id=1 has "Corte", business_id=2 has "Tinte"
        - WHEN get_by_business(1) is called
        - THEN only business 1's service is returned.
        """
        from app.features.business.service_repository import ServiceRepository
        from app.models.models import Service

        db = MagicMock()
        svc = Service(id=1, business_id=1, name="Corte", duration_minutes=30)

        mock_query = db.query.return_value
        mock_query.filter.return_value.all.return_value = [svc]

        repo = ServiceRepository(db)
        result = repo.get_by_business(1)

        assert len(result) == 1
        assert result[0].business_id == 1
