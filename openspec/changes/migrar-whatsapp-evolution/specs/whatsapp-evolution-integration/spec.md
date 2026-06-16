# whatsapp-evolution-integration Specification

## Purpose

Send and receive WhatsApp messages via self-hosted Evolution API (Baileys engine). Replaces Meta Cloud API: text via `sendText`, menus via `sendList`, webhook parsing, and multi-instance routing by `instance_name` with per-instance `apikey` authentication.

## Requirements

| # | Requirement | Keyword | Scenarios |
|---|------------|---------|-----------|
| 1 | Evolution Message Sending | MUST | Send success, Auth failure |
| 2 | Evolution Interactive Lists | MUST | Send list, >3 options |
| 3 | Evolution Webhook Receiving | MUST | Text receive, Non-message ignore |
| 4 | Multi-Instance Routing | MUST | Outgoing routing, Incoming resolution |
| 5 | Business Model Migration | MUST | Create fields, Lookup |
| 6 | List Response Parsing | MUST | Parse selection, Text distinction |

### Requirement: Evolution Message Sending

Text messages MUST be sent via `POST {EVOLUTION_API_URL}/message/sendText/{instance_name}` with header `apikey: {instance_apikey}`.

#### Scenario: Send text message

- GIVEN a valid Business
- WHEN sending text to a WhatsApp number
- THEN it POSTs to `/message/sendText/{instance_name}` with `apikey` header
- AND the body contains `number` and `text`

#### Scenario: Authentication failure

- GIVEN a Business with an invalid `instance_apikey`
- WHEN the system attempts to send
- THEN Evolution returns 401
- AND the system SHALL log and surface the error

### Requirement: Evolution Interactive Lists

Menus MUST be sent via `POST {EVOLUTION_API_URL}/message/sendList/{instance_name}`, replacing deprecated Meta interactive buttons.

#### Scenario: Send interactive list

- GIVEN a Business with valid credentials
- WHEN presenting options (services, barbers, dates)
- THEN it POSTs to `/message/sendList/{instance_name}` with body: `number`, `title`, `description`, `buttonText`, `footerText`, `values[]` + `rows[]`

#### Scenario: Lists exceed 3-option button limit

- GIVEN a menu with 5 options
- WHEN the system sends a list
- THEN `values[].rows[]` MUST contain all 5 options with unique `rowId` identifiers

### Requirement: Evolution Webhook Receiving

Incoming payloads `{instance, event, data.key.id, data.messageType}` MUST be parsed and the Business resolved by `instance`.

#### Scenario: Receive text message via webhook

- GIVEN Evolution POSTs `messages.upsert` with `instance: "barberia-latino"`, `messageType: "conversation"`, body `"Hola"`
- WHEN the webhook parses it
- THEN it extracts `instance_name`, `message_id`, `message_type`, and text body
- AND resolves the Business via `get_by_instance_name()`

#### Scenario: Ignore non-message events

- GIVEN Evolution sends `CONNECTION_UPDATE`
- WHEN the webhook receives it
- THEN the system SHALL return `{"status": "ignored"}` without processing

### Requirement: Multi-Instance Routing

Each Business MUST have its own instance. Outgoing messages MUST use its `instance_name` and `instance_apikey`.

#### Scenario: Route to correct instance

- GIVEN businesses "latino" (apikey "abc") and "chapinero" (apikey "def")
- WHEN "latino" sends a message
- THEN the request targets `/message/sendText/latino` with `apikey: abc`
- AND "chapinero" credentials are never used

#### Scenario: Incoming webhook resolves business

- GIVEN a webhook payload with `instance: "chapinero"`
- WHEN processed
- THEN `get_by_instance_name("chapinero")` resolves the correct Business

### Requirement: Business Model Migration

The `Business` model MUST replace `phone_number_id` with `instance_name` (unique, indexed string) and MUST add `instance_apikey` as an encrypted field.

#### Scenario: Business created with Evolution fields

- GIVEN a new business is registered
- WHEN the record is persisted
- THEN it MUST have `instance_name` (unique, indexed) and `instance_apikey` (encrypted)
- AND `phone_number_id` MUST NOT exist

#### Scenario: Repository lookup

- GIVEN a Business with `instance_name = "barberia-latino"`
- WHEN `get_by_instance_name("barberia-latino")` is called
- THEN it returns the matching Business

### Requirement: List Response Parsing

`listResponseMessage.singleSelectReply.selectedRowId` MUST be parsed from Evolution payloads as the equivalent of Meta's `interactive.button_reply.id`.

#### Scenario: Parse list selection response

- GIVEN a user selects from an interactive list
- WHEN the webhook receives `messageType: "listResponse"` with `selectedRowId: "service_1"`
- THEN the system extracts `interactive_id = "service_1"`
- AND routes through existing handler logic

#### Scenario: Distinguish text from list response

- GIVEN a payload with `messageType: "conversation"` and body `"quiero cancelar"`
- WHEN parsed
- THEN it is treated as a text message
- AND `interactive_id` remains `None`
