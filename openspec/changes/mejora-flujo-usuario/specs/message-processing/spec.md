# message-processing Specification

## Purpose

Procesamiento inmediato de mensajes de WhatsApp sin debounce de 10 segundos. Mantiene deduplicación vía `ProcessedMessage` scoped por `business_id`.

## Requirements

### Requirement: Immediate Message Processing

Los mensajes entrantes DEBEN procesarse inmediatamente al ser recibidos por el webhook. El sistema NO DEBE aplicar un debounce de 10 segundos.

#### Scenario: Message processed immediately

- GIVEN a WhatsApp message arrives via webhook
- WHEN the webhook handler receives the message
- THEN processing starts within 500ms of receipt
- AND the webhook response completes in under 1 second

#### Scenario: Rapid consecutive messages from same user

- GIVEN a user sends two messages within 1 second
- WHEN both messages arrive at the webhook
- THEN each message is processed independently
- AND no debounce blocks the second message

### Requirement: Remove BufferService Debounce

El `BufferService` con debounce DEBE ser eliminado. Su funcionalidad de deduplicación se mantiene vía `ProcessedMessage`.

#### Scenario: Duplicate message is still caught

- GIVEN message "wa-001" has already been processed for Business A
- WHEN the same message "wa-001" arrives again for Business A
- THEN the message is dropped as duplicate via `ProcessedMessage` check
- AND deduplication works without BufferService debounce

#### Scenario: Same msg_id for different businesses is NOT deduplicated

- GIVEN message "wa-001" has been processed for Business A
- WHEN message "wa-001" arrives for Business B
- THEN the message is processed normally (not dropped)

### Requirement: Webhook Response Under 1 Second

El webhook DEBE responder en menos de 1 segundo desde la recepción del mensaje. La deduplicación y el inicio del procesamiento ocurren dentro de ese plazo.

#### Scenario: Webhook response time

- GIVEN a WhatsApp message arrives
- WHEN the webhook handler processes it
- THEN the HTTP response is sent within 1 second of receipt
- AND processing continues asynchronously if needed
