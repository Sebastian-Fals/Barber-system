import asyncio
import logging
from datetime import datetime

import pytz
from starlette.concurrency import run_in_threadpool

from app.core.database import SessionLocal
from app.features.communication.conversation_service import ConversationService
from app.features.customers.repository import CustomerRepository
from app.models.models import MessageBuffer

logger = logging.getLogger(__name__)


class BufferService:
    @staticmethod
    async def add_message(customer_phone: str, message_body: str, phone_number_id: str, business_id: int):
        """
        Add a message to the user's buffer.
        If the buffer process is not running, start it.
        """
        should_start_task, customer_id = await run_in_threadpool(
            BufferService._add_message_sync, customer_phone, message_body, phone_number_id, business_id
        )

        if should_start_task:
            asyncio.create_task(
                BufferService.process_buffer_task(customer_id, phone_number_id, customer_phone, business_id)
            )

    @staticmethod
    def _add_message_sync(customer_phone: str, message_body: str, phone_number_id: str, business_id: int):
        """
        Synchronous part of adding message to buffer.
        """
        with SessionLocal() as db:
            # 1. Get/Create Customer (scoped by business_id)
            repo = CustomerRepository(db)
            customer = repo.get_by_phone(customer_phone, business_id)
            if not customer:
                # If customer doesn't exist, create IDLE customer
                customer = repo.create({"phone": customer_phone, "name": "Usuario", "business_id": business_id})

            customer_id = customer.id

            # 2. Get/Create Buffer
            buffer = db.query(MessageBuffer).filter(MessageBuffer.customer_id == customer_id).first()
            should_start_task = False

            if not buffer:
                buffer = MessageBuffer(customer_id=customer_id, content="", is_running=False)
                db.add(buffer)

            # 3. Update Buffer
            if buffer.content:
                buffer.content += f"\n{message_body}"
            else:
                buffer.content = message_body

            buffer.updated_at = datetime.now(pytz.UTC)

            if not buffer.is_running:
                buffer.is_running = True
                should_start_task = True

            db.commit()

            return should_start_task, customer_id

    @staticmethod
    async def process_buffer_task(customer_id: int, phone_number_id: str, customer_phone: str, business_id: int):
        logger.info(f"Started message buffer task for customer {customer_id}")

        while True:
            remaining = await run_in_threadpool(BufferService._check_remaining_time, customer_id)

            if remaining is None:
                break

            if remaining <= 0:
                final_content = await run_in_threadpool(BufferService._pop_buffer_content, customer_id)
                if final_content:
                    await BufferService._dispatch_message(phone_number_id, customer_phone, final_content, business_id)
                break

            await asyncio.sleep(remaining + 0.5)

    @staticmethod
    def _check_remaining_time(customer_id: int) -> float:
        with SessionLocal() as db:
            buffer = db.query(MessageBuffer).filter(MessageBuffer.customer_id == customer_id).first()
            if not buffer or not buffer.is_running:
                return None

            now = datetime.now(pytz.UTC)
            updated_at = buffer.updated_at
            if updated_at.tzinfo is None:
                updated_at = pytz.UTC.localize(updated_at)

            elapsed = (now - updated_at).total_seconds()
            return 10.0 - elapsed

    @staticmethod
    def _pop_buffer_content(customer_id: int) -> str:
        with SessionLocal() as db:
            buffer = db.query(MessageBuffer).filter(MessageBuffer.customer_id == customer_id).first()
            if not buffer:
                return None

            content = buffer.content
            buffer.content = ""
            buffer.is_running = False
            db.commit()

            return content

    @staticmethod
    async def _dispatch_message(phone_number_id: str, customer_phone: str, text: str, business_id: int):
        logger.info(f"Dispatching buffered message for {customer_phone}: {text[:30]}...")
        await run_in_threadpool(BufferService._dispatch_sync, phone_number_id, customer_phone, text, business_id)

    @staticmethod
    def _dispatch_sync(phone_number_id: str, customer_phone: str, text: str, business_id: int):
        with SessionLocal() as db:
            service = ConversationService(db, phone_number_id, business_id)
            service.handle_incoming_message(customer_phone, text, "text")
