"""
RED tests for Service model.

Spec: booking-flow — Service Selection Step
Design: Service model with id, business_id, name, duration_minutes.
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.database import Base


@pytest.fixture
def engine():
    """In-memory SQLite engine for Service model testing."""
    return create_engine("sqlite:///:memory:", echo=False)


@pytest.fixture
def db_session(engine):
    """Create tables, yield session, then drop."""
    from app.models.models import Service  # noqa: F401

    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    Base.metadata.drop_all(engine)


class TestServiceModel:
    """RED: Service model with business_id FK, name, and duration_minutes."""

    def test_create_service_with_valid_data(self, db_session):
        """
        Scenario: Create a Service with business_id, name, and custom duration.
        - GIVEN a business_id=1
        - WHEN a Service is created with name="Corte" and duration_minutes=30
        - THEN the service is persisted with the correct values.
        """
        from app.models.models import Service

        service = Service(
            business_id=1,
            name="Corte",
            duration_minutes=30,
        )
        db_session.add(service)
        db_session.commit()

        result = db_session.query(Service).filter(Service.id == service.id).first()
        assert result is not None
        assert result.name == "Corte"
        assert result.business_id == 1
        assert result.duration_minutes == 30

    def test_service_default_duration_is_60(self, db_session):
        """
        Scenario: Create a Service without specifying duration.
        - GIVEN no duration_minutes is provided
        - WHEN a Service is created with name="Barba"
        - THEN duration_minutes defaults to 60.
        """
        from app.models.models import Service

        service = Service(
            business_id=1,
            name="Barba",
        )
        db_session.add(service)
        db_session.commit()

        result = db_session.query(Service).filter(Service.id == service.id).first()
        assert result.duration_minutes == 60

    def test_services_are_scoped_by_business(self, db_session):
        """
        Scenario: Multiple businesses have different services.
        - GIVEN business 1 has "Corte" and business 2 has "Tinte"
        - WHEN querying services for business 1
        - THEN only business 1's services are returned.
        """
        from app.models.models import Service

        s1 = Service(business_id=1, name="Corte", duration_minutes=30)
        s2 = Service(business_id=2, name="Tinte", duration_minutes=45)
        db_session.add_all([s1, s2])
        db_session.commit()

        results = db_session.query(Service).filter(Service.business_id == 1).all()
        assert len(results) == 1
        assert results[0].name == "Corte"
        assert results[0].business_id == 1
