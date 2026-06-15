# booking-flow Specification

## Purpose

Flujo de reserva unificado con paso SELECT_SERVICE implementado. Tanto el modo AI como el no-AI comparten la misma UX de botones interactivos. El LLM solo clasifica intención y extrae entidades, no genera UI.

## Requirements

### Requirement: Unified Booking Flow Order

El flujo de reserva DEBE seguir el orden: SERVICE → BARBER → DATE → SLOT → CONFIRM, tanto en modo AI como no-AI.

#### Scenario: Happy path booking

- GIVEN a user sends "reservar" to the WhatsApp bot
- WHEN the system initiates the booking flow
- THEN the user is first prompted to select a service (Corte, Barba, etc.)
- THEN to select a barber
- THEN to select a date
- THEN to select a time slot
- THEN to confirm the reservation

#### Scenario: User cancels mid-flow

- GIVEN a user is at the BARBER selection step
- WHEN the user sends "cancelar"
- THEN the booking flow is terminated
- AND the user returns to the main menu

### Requirement: Service Selection Step

El sistema DEBE presentar opciones de servicio (corte, barba, etc.) como botones interactivos ANTES de la selección de barbero.

#### Scenario: Service options displayed

- GIVEN a user enters the booking flow
- WHEN the system reaches the SERVICE step
- THEN interactive buttons for available services are shown
- AND the user MUST select a service before proceeding to barber selection

#### Scenario: Invalid service selection

- GIVEN a user is at the SERVICE selection step
- WHEN the user sends text that does NOT match any service button
- THEN the system MUST re-prompt with the available service options

### Requirement: AI and Non-AI Share Same UI

El modo AI y no-AI DEBEN usar los mismos botones interactivos de WhatsApp. El LLM NO DEBE generar UI; solo clasifica intención y extrae entidades.

#### Scenario: AI mode uses same buttons

- GIVEN the system is in AI mode
- WHEN presenting options for service, barber, date, or slot selection
- THEN the same interactive button payloads are used as in non-AI mode
- AND the LLM does NOT generate button markup

#### Scenario: Non-AI mode uses same buttons

- GIVEN the system is in non-AI mode (rule-based)
- WHEN presenting options for any booking step
- THEN the same interactive button payloads are used as in AI mode
