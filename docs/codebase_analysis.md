# Informe de Análisis del Código: Sistema de Citas WhatsApp

## 1. Resumen Ejecutivo
El proyecto tiene una estructura funcional basada en **FastAPI** con **SQLAlchemy**, pero presenta síntomas de crecimiento orgánico que dificultan la mantenibilidad. El núcleo del problema reside en la **centralización excesiva de lógica** en pocos servicios ("God Classes"), especialmente `ConversationService`, y un manejo de fechas (tz-naive vs tz-aware) que es propenso a errores en producción.

## 2. Análisis Estructural y Arquitectura

### Estructura de Directorios
- **Bien**: Separación clara entre `api`, `core`, `models` y `services`.
- **Mal**: `services/` contiene la lógica de negocio mezclada con orquestación. Faltan capas intermedias como `Repositories` para el acceso a datos.

### Patrones de Diseño Detectados
- **Service Layer**: Implementado, pero los servicios hacen demasiado (lógica de negocio + acceso a DB + llamadas a API externas).
- **Monolith**: Todo el manejo del flujo de conversación reside en una sola clase gigante.

## 3. Revisión Detallada por Componente

### A. `app/services/conversation_service.py` (Critical Hotspot)
Este es el archivo más problemático (500+ líneas).
- **Problema (God Class)**: Maneja la máquina de estados, lógica de presentación (menús), interacción con LLM y lógica de reserva. Violación del Principio de Responsabilidad Única (SRP).
- **Estado Implícito**: El manejo de estados (`_handle_interactive`, `_process_booking_intent`) es un switch-case gigante difícil de testear y extender.
- **Refactor Recomendado**:
    - Implementar el **Patrón State** o **Chain of Responsibility**.
    - Extraer "Message Handlers" independientes: `BookingHandler`, `MenuHandler`, `QnAHandler`.
    - Mover la lógica de formateo de texto (strings de menús) a un módulo de `templates` o `views`.

### B. `app/services/booking_service.py`
- **Problema (Manejo de Fechas)**: Mezcla `datetime.now()` (local del sistema) con fechas que vienen de Google Calendar (UTC o Aware).
    - *Riesgo*: `current_slot < now` fallará o dará resultados erróneos si el servidor no está en la misma zona horaria que `settings.TIMEZONE`.
    - *Solución*: Usar siempre **UTC** internamente o objetos `datetime` con zona horaria explícita (`tz-aware`).
- **Problema (Lógica de Negocio en DB Query)**: La lógica de filtrado de slots (`filter_slots_by_period`) debería ser más robusta o delegarse al frontend/cliente (en este caso WhatsApp).

### C. `app/main.py`
- **Problema (Lógica en Lifespan)**: La lógica de suscripción a Webhooks es compleja y difícil de manejar errores dentro del startup. Si falla un webhook, ¿debería fallar el arranque?
- **Recomendación**: Mover la inicialización de webhooks a una tarea en segundo plano (`BackgroundTasks`) o un script de inicialización separado.

### D. `app/models/models.py`
- **Bien**: Definiciones claras.
- **Mejora**: `CustomerData` (Enum) y `conversation_state` y `conversation_data` (Strings/JSON) sugieren que se necesita una tabla de `Sessions` separada para no "ensuciar" la tabla de `Customer` con datos efímeros de navegación.

## 4. Buenas y Malas Prácticas Identificadas

### ✅ Buenas Prácticas
- Uso de `FastAPI` y `Pydantic` (validación implícita).
- Inyección de dependencias para `db: Session`.
- Logging configurado centralmente (`app.core.logging_config`).
- Uso de `Enum` para estados y tipos constantes.

### ❌ Malas Prácticas / Riesgos
- **Hardcoding**: Strings mágicos en `conversation_service.py` (ej. "Texto del menú").
- **Manejo de Errores Silencioso**: Bloques `try: ... except Exception: pass` o solo log en `booking_service.py`. Esto oculta bugs graves.
- **Sin Repositorios**: Consultas SQL (`db.query(...)`) esparcidas por todos los servicios. Si cambia el modelo, hay que refactorizar múltiples archivos.
- **Global Settings**: Uso directo de `settings` en lo profundo de la lógica de negocio dificulta los tests unitarios.

## 5. Roadmap de Refactorización

### Fase 1: Estabilización (Inmediato)
1.  **Arreglar Datetime**: Estandarizar todo el manejo de fechas a objetos `aware` usando `pytz` o `zoneinfo`.
2.  **Repository Pattern**: Crear `app/repositories/` y mover las queries de `BookingService` y `ConversationService` allí.

### Fase 2: Modularización (Corto Plazo)
3.  **Refactor ConversationService**:
    - Crear clase base `ConversationHandler`.
    - Crear subclases: `AppointmentHandler`, `QueryHandler`.
    - El `ConversationService` solo actúa como "Router" delegando el mensaje al handler correcto según el estado.

### Fase 3: Limpieza (Medio Plazo)
4.  **Extracción de Textos**: Mover todos los textos de respuesta a un archivo YAML o JSON (`locales/es.json`) para facilitar cambios de copy sin tocar código.
5.  **Tests Unitarios**: El código actual es difícil de testear por el alto acoplamiento. La modularización permitirá tests aislados.
