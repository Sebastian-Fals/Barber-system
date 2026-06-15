# multi-tenant Specification

## Purpose

Aislamiento de datos por negocio. El sistema soporta múltiples negocios simultáneos, cada uno con su propio número WhatsApp, clientes, citas, y configuraciones independientes.

## Requirements

### Requirement: Business-scoped Customer Identity

Un cliente se identifica por la tupla `(phone_hash, business_id)`, no solo por `phone_hash`. El mismo número de teléfono PUEDE existir en distintos negocios sin conflicto.

#### Scenario: Same phone across two businesses

- GIVEN Business A has customer with phone_hash "abc123"
- WHEN Business B creates a customer with the same phone_hash "abc123"
- THEN both customers are created independently
- AND each is scoped to its respective business_id

#### Scenario: Duplicate phone within same business

- GIVEN Business A already has customer with phone_hash "abc123"
- WHEN Business A tries to create another customer with phone_hash "abc123"
- THEN the operation MUST fail with a uniqueness constraint violation

#### Scenario: Customer lookup scoped by business

- GIVEN Business A has customer with phone_hash "abc123" and Business B has customer with phone_hash "xyz789"
- WHEN Business A queries `get_by_phone("abc123", business_id=A)`
- THEN only Business A's customer is returned
- AND Business B's customer is never exposed

### Requirement: Webhook Resolves Business ID First

Al recibir un webhook de WhatsApp, el sistema DEBE resolver el `business_id` desde `phone_number_id` ANTES de cualquier procesamiento. Toda la cadena downstream (handlers, repositorios, servicios) recibe `business_id` explícitamente.

#### Scenario: Webhook with known phone_number_id

- GIVEN phone_number_id "123456" maps to Business A
- WHEN a WhatsApp webhook arrives with phone_number_id "123456"
- THEN business_id is resolved immediately
- AND all downstream handlers receive the resolved business_id

#### Scenario: Webhook with unknown phone_number_id

- GIVEN phone_number_id "999999" does NOT map to any business
- WHEN a WhatsApp webhook arrives with phone_number_id "999999"
- THEN the webhook MUST return an error or be silently ignored
- AND no un-scoped data is created

### Requirement: Message Deduplication Scoped by Business

La deduplicación de mensajes DEBE usar la clave compuesta `(msg_id, business_id)`. Un mensaje duplicado en un negocio NO DEBE bloquear el mismo `msg_id` en otro negocio.

#### Scenario: Same msg_id across two businesses

- GIVEN Business A has processed msg_id "wa-001"
- WHEN Business B receives the same msg_id "wa-001"
- THEN Business B's message is processed normally (not deduplicated)

#### Scenario: Duplicate msg_id within same business

- GIVEN Business A has processed msg_id "wa-001"
- WHEN Business A receives msg_id "wa-001" again
- THEN the message is silently dropped as duplicate

### Requirement: Appointment Data Scoped by Business

Las citas DEBEN incluir `business_id` denormalizado. Las queries de appointments DEBEN filtrar por `business_id`.

#### Scenario: List appointments for one business

- GIVEN Business A has 3 appointments and Business B has 2 appointments
- WHEN listing appointments for Business A
- THEN exactly 3 appointments are returned
- AND no appointments from Business B appear

### Requirement: Conversation History Scoped by Business

El historial de conversación DEBE filtrarse por `business_id`. Un negocio NUNCA DEBE acceder al historial de otro.

#### Scenario: Conversation history isolation

- GIVEN Business A and Business B each have conversation history with customer phone "555-1234"
- WHEN retrieving conversation history for Business A and phone "555-1234"
- THEN only Business A's history is returned
