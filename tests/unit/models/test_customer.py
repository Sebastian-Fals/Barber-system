"""
RED tests for Customer model composite unique constraint (phone_hash, business_id).

Spec scenarios:
  - Same phone across two businesses → no conflict
  - Same phone + same business → IntegrityError
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import Base


@pytest.fixture
def engine():
    """In-memory SQLite engine for constraint testing."""
    return create_engine("sqlite:///:memory:", echo=False)


@pytest.fixture
def db_session(engine):
    """Create tables in the schema as defined by current models, yield session, then drop."""
    # Import late so the model class is current at fixture execution time
    from app.models.models import Customer  # noqa: F401

    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    Base.metadata.drop_all(engine)


class TestCustomerMultiTenant:
    """RED: composite unique constraint (phone_hash, business_id)."""

    def test_same_phone_two_businesses_no_conflict(self, db_session):
        """
        Scenario: Same phone across two businesses.
        - GIVEN Business A has customer with phone_hash "abc123"
        - WHEN Business B creates a customer with the same phone_hash
        - THEN both customers are created independently.
        """
        from app.models.models import Customer

        c1 = Customer(
            phone="+573001234567",
            name="Cliente A",
            business_id=1,
        )
        db_session.add(c1)
        db_session.commit()

        c2 = Customer(
            phone="+573001234567",
            name="Cliente B",
            business_id=2,
        )
        db_session.add(c2)
        db_session.commit()  # MUST NOT raise IntegrityError

        # Verify both exist
        results = (
            db_session.query(Customer).filter(Customer.phone_hash == c1.phone_hash).all()  # same phone → same hash
        )
        assert len(results) == 2
        assert {r.business_id for r in results} == {1, 2}

    def test_duplicate_phone_same_business_integrity_error(self, db_session):
        """
        Scenario: Duplicate phone within same business.
        - GIVEN Business A already has customer with phone_hash "abc123"
        - WHEN Business A tries to create another customer with same phone_hash
        - THEN IntegrityError MUST be raised.
        """
        from app.models.models import Customer

        c1 = Customer(
            phone="+573001234567",
            name="Cliente Uno",
            business_id=1,
        )
        db_session.add(c1)
        db_session.commit()

        c2 = Customer(
            phone="+573001234567",
            name="Cliente Dos",
            business_id=1,
        )
        db_session.add(c2)
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()
