"""
RED tests for ProcessedMessage composite unique constraint (message_id, business_id).

Spec scenarios:
  - Same msg_id across two businesses → not deduplicated
  - Same msg_id within same business → deduplicated (IntegrityError)
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
    from app.models.models import ProcessedMessage  # noqa: F401

    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    Base.metadata.drop_all(engine)


class TestProcessedMessageMultiTenant:
    """RED: composite unique constraint (message_id, business_id)."""

    def test_same_msg_id_two_businesses_no_conflict(self, db_session):
        """
        Scenario: Same msg_id across two businesses.
        - GIVEN Business A has processed msg_id "wa-001"
        - WHEN Business B receives the same msg_id "wa-001"
        - THEN Business B's message is processed normally (not deduplicated).
        """
        from app.models.models import ProcessedMessage

        msg1 = ProcessedMessage(message_id="wa-001", business_id=1)
        db_session.add(msg1)
        db_session.commit()

        msg2 = ProcessedMessage(message_id="wa-001", business_id=2)
        db_session.add(msg2)
        db_session.commit()  # MUST NOT raise IntegrityError

        results = db_session.query(ProcessedMessage).filter(ProcessedMessage.message_id == "wa-001").all()
        assert len(results) == 2
        assert {r.business_id for r in results} == {1, 2}

    def test_duplicate_msg_id_same_business_integrity_error(self, db_session):
        """
        Scenario: Duplicate msg_id within same business.
        - GIVEN Business A has processed msg_id "wa-001"
        - WHEN Business A receives msg_id "wa-001" again
        - THEN IntegrityError MUST be raised (message silently dropped).
        """
        from app.models.models import ProcessedMessage

        msg1 = ProcessedMessage(message_id="wa-001", business_id=1)
        db_session.add(msg1)
        db_session.commit()

        msg2 = ProcessedMessage(message_id="wa-001", business_id=1)
        db_session.add(msg2)
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()
