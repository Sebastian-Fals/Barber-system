from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.buffer_service import BufferService


# Mock starlette.concurrency for async tests since we don't have a real app loop easily
@pytest.fixture
def mock_run_in_threadpool():
    with patch("app.services.buffer_service.run_in_threadpool", new_callable=AsyncMock) as mock:
        yield mock


def test_add_message_sync_creates_buffer():
    with patch("app.services.buffer_service.SessionLocal") as mock_session_cls, patch(
        "app.services.buffer_service.CustomerRepository"
    ) as MockRepo:
        mock_db = MagicMock()
        mock_session_cls.return_value.__enter__.return_value = mock_db

        mock_repo_instance = MockRepo.return_value
        mock_customer = MagicMock(id=1)
        mock_repo_instance.get_by_phone.return_value = mock_customer

        # Buffer not found
        mock_db.query.return_value.filter.return_value.first.return_value = None

        should_start, cid = BufferService._add_message_sync("57300", "Hi", "pid", 1)

        assert should_start is True
        assert cid == 1
        mock_db.add.assert_called()  # Created


def test_add_message_sync_appends_buffer():
    with patch("app.services.buffer_service.SessionLocal") as mock_session_cls, patch(
        "app.services.buffer_service.CustomerRepository"
    ) as MockRepo:
        mock_db = MagicMock()
        mock_session_cls.return_value.__enter__.return_value = mock_db

        mock_repo_instance = MockRepo.return_value
        mock_customer = MagicMock(id=1)
        mock_repo_instance.get_by_phone.return_value = mock_customer

        # Buffer found and running
        mock_buffer = MagicMock()
        mock_buffer.content = "Hello"
        mock_buffer.is_running = True
        mock_db.query.return_value.filter.return_value.first.return_value = mock_buffer

        should_start, cid = BufferService._add_message_sync("57300", "World", "pid", 1)

        assert should_start is False  # Already running
        assert mock_buffer.content == "Hello\nWorld"


@pytest.mark.asyncio
async def test_add_message_spawns_task(mock_run_in_threadpool):
    # Setup mock return from sync function
    # (should_start=True, customer_id=1)
    mock_run_in_threadpool.return_value = (True, 1)

    with patch("app.services.buffer_service.asyncio.create_task") as mock_create_task:
        await BufferService.add_message("57300", "Hi", "pid", 1)

        mock_create_task.assert_called_once()  # Should spawn task


@pytest.mark.asyncio
async def test_process_dispatch():
    # Test internal dispatch logic
    mock_run_in_threadpool = AsyncMock()

    with patch("app.services.buffer_service.run_in_threadpool", side_effect=mock_run_in_threadpool):
        # We Mock _dispatch_sync calls
        await BufferService._dispatch_message("pid", "57300", "Content", 1)

        assert mock_run_in_threadpool.call_count == 1
