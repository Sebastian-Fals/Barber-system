# Exploration: Migración WhatsApp Cloud API → Evolution API

## Current State

El sistema usa WhatsApp Cloud API (Meta) para envío y recepción de mensajes. La integración actual tiene 3 capas:

1. **Capa de envío** — `app/features/communication/whatsapp_service.py` (68 líneas)
   - `WhatsAppService.send_message(phone_number_id, to, body)` → `POST graph.facebook.com/v18.0/{phone_number_id}/messages`
   - `WhatsAppService.send_interactive_button(phone_number_id, to, body, buttons)` → mismo endpoint, `type: interactive`
   - Autenticación: `Bearer {WHATSAPP_API_TOKEN}` (un token global)

2. **Capa de recepción** — `app/api/webhook.py` (139 líneas)
   - `GET /api/v1/webhook` — verificación con `hub.verify_token`
   - `POST /api/v1/webhook` — parsea payload Meta: `entry[].changes[].value.metadata.phone_number_id`
   - Resuelve `business_id` vía `BusinessRepository.get_by_phone_number_id()`
   - Extrae `msg_type`: `"text"` (con `text.body`) o `"interactive"` (con `interactive.button_reply.id`)
   - Deduplicación: `ProcessedMessage` por `(message_id, business_id)`
   - Dispatch background con `business_id` propagado

3. **Capa de handlers** — `app/services/handlers/*.py` (+ conversation_service.py)
   - Todos reciben `phone_number_id` en constructor y lo usan para enviar respuestas
   - `booking_handler.py`: 14+ llamadas a `whatsapp_service.send_message/send_interactive_button`
   - `welcome_handler.py`: 9+ llamadas (menú principal, info, mis citas)
   - `query_handler.py`: 16+ llamadas (respuestas AI, booking asistido, cancelación)
   - `scheduling/service.py`: 2 llamadas (recordatorios 24h y 1h)

4. **Modelo de datos** — `Business.phone_number_id` (String, unique, index)
   - Es un identificador de Meta (ej. `86196104034`) que se usa como `{phone_number_id}` en la URL de Graph API

### Flujo completo actual
```
WhatsApp User → Meta → POST /api/v1/webhook → webhook.py
  → parse entry[].changes[].value.metadata.phone_number_id
  → BusinessRepository.get_by_phone_number_id() → business_id
  → ProcessedMessage dedup check
  → process_background_message(phone_number_id, from, body, type, interactive_id, business_id)
    → ConversationService(db, phone_number_id, business_id)
      → Handler(db, phone_number_id, business_id)
        → whatsapp_service.send_message(phone_number_id, to, body)
```

## Evolution API — Investigación

### Arquitectura

Evolution API v2 es un servidor Node.js (Baileys + Express) que se self-hostea vía Docker. Expone una REST API + webhooks. Soporta dos modos de integración:

| Modo | Motor | Conexión | Botones | Costo |
|------|-------|----------|---------|-------|
| `WHATSAPP-BAILEYS` | Baileys (no-oficial) | QR code | ❌ DISCONTINUED | $0 (solo hosting) |
| `WHATSAPP-BUSINESS` | Meta Cloud API (proxy) | Token permanente | ✅ | Meta pricing |

### 🔴 CRÍTICO: Send Buttons está DISCONTINUADO en Baileys

La [página oficial de features](https://doc.evolution-api.com/v2/en/configuration/available-resources.md) dice explícitamente:

> **Send Buttons (Discontinued) ❌ — Only works on cloud API**

Esto significa que si usamos `WHATSAPP-BAILEYS` (la opción gratuita), NO podemos enviar interactive buttons. Todo el flujo de booking actual depende de botones:
- Menú principal: `menu_book`, `menu_my_appts`, `menu_info`
- Selección de servicio: `service_{id}`
- Selección de barbero: `barber_{id}`
- Selección de fecha: `date_{YYYY-MM-DD}`
- Selección de hora: `time_{HH:MM}`
- Confirmación: `confirm_yes`, `confirm_no`
- Cancelación: `cancel_appt_{id}`, `cancel_flow`
- Paginación: `page_{n}`

### Alternativa: Send List (en staging)

Evolution soporta **Send List** (marcado como `✅ Testing` en staging). Permite enviar menús con opciones seleccionables:

```
POST /message/sendList/{instance}
{
  "number": "573001234567",
  "title": "Selecciona un servicio",
  "description": "Estos son nuestros servicios",
  "buttonText": "Ver servicios",
  "footerText": "Barbería Test",
  "values": [
    {
      "title": "Cortes",
      "rows": [
        { "title": "Corte Clásico", "description": "30 min - $15", "rowId": "service_1" },
        { "title": "Corte Premium", "description": "45 min - $25", "rowId": "service_2" }
      ]
    }
  ]
}
```

Ventajas vs botones:
- Soporta más de 3 opciones (los botones están limitados a 3)
- Agrupación por secciones
- Descripciones con más texto
- El `rowId` equivale a nuestro `interactive_id` actual

Desventajas:
- La respuesta del usuario llega como `listResponseMessage` con `singleSelectReply.selectedRowId` — formato diferente al `interactive.button_reply.id` actual
- El botón para abrir la lista ocupa espacio
- La UX es diferente (el usuario debe tocar "Ver opciones" primero)

### Creación de instancias

```
POST /instance/create
{
  "instanceName": "barberia-test",    // nombre único de la instancia
  "token": "apikey-opcional",        // API key para esta instancia
  "number": "573001234567",          // número dueño (con código país)
  "integration": "WHATSAPP-BAILEYS", // o WHATSAPP-BUSINESS
  "qrcode": true,                    // generar QR para escanear
  "webhook": {
    "url": "https://miapp.com/api/v1/webhook",
    "events": ["MESSAGES_UPSERT"],
    "enabled": true
  }
}
```

La respuesta incluye:
- `instance.instanceName` — nombre confirmado
- `hash.apikey` — API key generada (si no se especificó)
- `instance.status` — `"created"` (luego `"open"` tras escanear QR)

### Envío de mensajes (Baileys)

```
POST /message/sendText/{instance}
Headers: apikey: {instance_apikey}
Body: { "number": "573001234567", "text": "Hola" }
```

```
POST /message/sendList/{instance}
Headers: apikey: {instance_apikey}
Body: { "number": "...", "title": "...", "description": "...", "buttonText": "...", "footerText": "...", "values": [...] }
```

### Webhooks entrantes

El webhook se configura por instancia. El payload del evento `MESSAGES_UPSERT` tiene esta estructura (formato Baileys):

```json
{
  "event": "messages.upsert",
  "instance": "barberia-test",
  "data": {
    "key": {
      "remoteJid": "573001234567@s.whatsapp.net",
      "fromMe": false,
      "id": "BAE5A123456789"
    },
    "messageTimestamp": "1717781848",
    "pushName": "Juan",
    "messageType": "conversation",
    "message": {
      "conversation": "Hola quiero una cita"
    }
  }
}
```

Para respuestas de List:
```json
{
  "message": {
    "listResponseMessage": {
      "title": "Seleccionaste X",
      "singleSelectReply": { "selectedRowId": "service_1" }
    }
  },
  "messageType": "listResponse"
}
```

**Diferencias clave vs Meta webhook:**
- No hay `hub.verify_token`/`hub.challenge` — Evolution llama al webhook directamente tras configurarlo
- El `instance` name identifica al negocio (reemplaza `phone_number_id`)
- El `data.key.id` es el `message_id` para deduplicación
- No existe `interactive.button_reply.id` → en su lugar `listResponseMessage.singleSelectReply.selectedRowId`

### Autenticación

- **Global API key**: `AUTHENTICATION_API_KEY` en `.env` de Evolution — protege el endpoint `/instance/create`
- **Instance API key**: generada por instancia (en `hash.apikey`) — se usa en header `apikey` para todos los endpoints de mensajería de esa instancia

Nuestro `WhatsAppService` necesitará almacenar y usar la API key correcta por instancia.

### Rate limits

Evolution (Baileys) no tiene rate limits documentados — hereda los límites de WhatsApp Web: ~50-80 mensajes/minuto por número. Con `WHATSAPP-BUSINESS`, aplican los rate limits de Meta (250 msgs/segundo para cuentas verificadas, 1000/segundo en alto volumen).

## Comparación API

| Aspecto | Meta Cloud API | Evolution API (Baileys) |
|---------|---------------|--------------------------|
| **Endpoint envío texto** | `POST graph.facebook.com/v18.0/{phone_id}/messages` | `POST {evolution_url}/message/sendText/{instance}` |
| **Endpoint envío botones** | Mismo que texto, `type: interactive` | ❌ DISCONTINUED — usar `POST /message/sendList/{instance}` |
| **Webhook entrante** | `POST /webhook` con verificación `hub.verify_token` | `POST /webhook` (configurado por instancia, sin verificación challenge) |
| **Formato payload entrada** | `{object, entry[].changes[].value}` anidado | `{event, instance, data: {key, message, messageType}}` plano |
| **Identificador negocio** | `metadata.phone_number_id` (numérico Meta) | `instance` (string, nombre de instancia) |
| **Auth envío** | `Bearer {WHATSAPP_API_TOKEN}` global | `apikey: {instance_apikey}` por instancia |
| **Multi-número** | Un WABA, múltiples phone_number_ids | Una instancia por número |
| **Botones interactivos** | `interactive.button.reply.id` | N/A (List: `listResponseMessage.singleSelectReply.selectedRowId`) |
| **Rate limits** | 250-1000 msgs/seg | ~50-80 msgs/min (WhatsApp Web) |
| **Costo** | Por conversación (Meta pricing) | $0 (hosting propio) |

## Cambios necesarios en el código

### 1. `app/core/config.py` — Nuevas variables de entorno

```python
# WhatsApp — se eliminan WHATSAPP_API_TOKEN y WHATSAPP_VERIFY_TOKEN
# Se reemplazan por:
EVOLUTION_API_URL: str  # ej. http://localhost:8080
EVOLUTION_GLOBAL_API_KEY: str  # AUTHENTICATION_API_KEY de Evolution (para admin/crear instancias)
```

**Nota**: `WHATSAPP_API_TOKEN` y `WHATSAPP_VERIFY_TOKEN` dejan de ser necesarios.

### 2. `.env.example` — Actualizar

```env
# === EVOLUTION API ===
EVOLUTION_API_URL="http://localhost:8080"
EVOLUTION_GLOBAL_API_KEY="429683C4C977415CAAFCCE10F7D57E11"
```

### 3. `app/models/models.py` — `Business`

**Opción A (recomendada)**: Renombrar `phone_number_id` → `instance_name`
- Columna: `instance_name = Column(String, unique=True, index=True, nullable=False)`
- Requiere migración de BD (Alembic): renombrar columna, migrar datos existentes

**Opción B (mínimo cambio)**: Mantener nombre de columna, cambiar semántica
- `phone_number_id` ahora almacena el `instanceName` de Evolution
- Sin migración de esquema, solo cambio semántico en código

**Recomiendo Opción A** para claridad semántica, con migración.

### 4. `app/features/business/repository.py`

```python
# Renombrar método
def get_by_instance_name(self, instance_name: str) -> Optional[Business]:
    return self.db.query(self.model).filter(self.model.instance_name == instance_name).first()
```

### 5. `app/features/communication/whatsapp_service.py` — Reescritura completa

Cambios estructurales:
- Eliminar `self.base_url = "https://graph.facebook.com/v18.0"`
- Eliminar `self.token = settings.WHATSAPP_API_TOKEN`
- Agregar `self.base_url = settings.EVOLUTION_API_URL`
- Cada método recibe `instance_name` + `instance_apikey` en vez de `phone_number_id`
- `send_message()` → `POST /message/sendText/{instance_name}`, header `apikey: {instance_apikey}`
- `send_interactive_button()` → **se reemplaza por `send_list()`** usando `/message/sendList/{instance_name}`
- El formato del payload cambia: de `{messaging_product, to, type, interactive}` a `{number, title, description, buttonText, footerText, values}`

**Nuevo método `send_list()`**:
```python
def send_list(
    self, instance_name: str, instance_apikey: str,
    to_number: str, title: str, description: str,
    button_text: str, footer_text: str, values: list
):
    url = f"{self.base_url}/message/sendList/{instance_name}"
    headers = {"apikey": instance_apikey, "Content-Type": "application/json"}
    data = {
        "number": to_number,
        "title": title,
        "description": description,
        "buttonText": button_text,
        "footerText": footer_text,
        "values": values,
    }
    ...
```

**Gestión de API keys por instancia**: el `WhatsAppService` necesita saber la API key de cada instancia. Opciones:
- Pasar `instance_apikey` en cada llamada (el caller lo obtiene del `Business`)
- El `ConversationService` ya tiene el `business_id`, puede hacer un lookup

### 6. `app/api/webhook.py` — Cambios en recepción

Cambios necesarios:
- **Eliminar** `GET /webhook` (verificación con `hub.verify_token`) — Evolution no lo usa
- **Reescribir** `POST /webhook` para parsear el formato de Evolution:
  ```python
  # Formato actual (Meta):
  phone_number_id = value.get("metadata", {}).get("phone_number_id")

  # Formato nuevo (Evolution):
  instance_name = body.get("instance")
  event = body.get("event")        # "messages.upsert"

  # Solo procesar MESSAGES_UPSERT
  if event != "messages.upsert":
      return {"status": "ignored"}

  # Business resolution
  business = biz_repo.get_by_instance_name(instance_name)  # antes: get_by_phone_number_id
  ```
- El parseo de mensajes cambia:
  ```python
  data = body.get("data", {})
  msg_id = data.get("key", {}).get("id")
  from_number = data.get("key", {}).get("remoteJid", "").split("@")[0]
  message_type = data.get("messageType")  # "conversation" o "listResponse"
  msg_body = ""
  interactive_id = None

  if message_type == "conversation":
      msg_body = data.get("message", {}).get("conversation", "")
  elif message_type == "listResponse":
      interactive_id = data.get("message", {}).get("listResponseMessage", {}).get("singleSelectReply", {}).get("selectedRowId")
  ```
- El dispatch a background tasks sigue igual (pasa `instance_name` en vez de `phone_number_id`)

### 7. Todos los handlers — Cambio de parámetros

En todos los archivos de handler (`base_handler.py`, `welcome_handler.py`, `booking_handler.py`, `query_handler.py`) y en `conversation_service.py`:

- El parámetro de constructor `phone_number_id: str` pasa a llamarse `instance_name: str`
- Todas las llamadas a `whatsapp_service.send_message(phone_number_id, ...)` → `whatsapp_service.send_message(instance_name, instance_apikey, ...)`
- Todas las llamadas a `whatsapp_service.send_interactive_button(...)` → migrar a `whatsapp_service.send_list(...)`

### 8. `app/features/scheduling/service.py` — Recordatorios

```python
# Líneas 98, 114 — recordatorios 24h y 1h
whatsapp_service.send_interactive_button(
    business.phone_number_id, customer.phone, msg, buttons
)
# →
whatsapp_service.send_list(
    business.instance_name, business.instance_apikey, customer.phone,
    title, description, button_text, footer_text, values
)
```

### 9. Scripts CLI — Actualizar

- `scripts/add_business.py`: `phone_number_id` → `instance_name`
- `scripts/admin_cli.py`: ídem
- `scripts/create_business.py`: ídem
- `reset_db.py`: actualizar seed data

### 10. Tests

- `tests/unit/api/test_webhook.py` (313 líneas) — reescribir payloads de Meta → Evolution
- `tests/unit/features/communication/test_conversation_service.py` — actualizar mocks para `instance_name`
- `tests/conftest.py` — actualizar fixture de `Business`

### 11. Migración de base de datos (Alembic)

```bash
alembic revision --autogenerate -m "rename phone_number_id to instance_name on businesses"
```

La migración debe:
1. Renombrar columna `phone_number_id` → `instance_name`
2. Agregar columna `instance_apikey` (EncryptedString, nullable) — solo si usamos `WHATSAPP-BAILEYS`, necesitamos almacenar la API key de cada instancia

### 12. `requirements.txt`

**No se requieren nuevas dependencias de Python.** El proyecto ya tiene `requests` (HTTP) y `tenacity` (retries). Evolution API se comunica vía REST estándar.

**Dependencia de infraestructura nueva**: Docker para hostear Evolution API. El `docker-compose.yml` recomendado:

```yaml
services:
  evolution-api:
    image: atendai/evolution-api:v2.1.1
    ports:
      - "8080:8080"
    environment:
      - AUTHENTICATION_API_KEY=${EVOLUTION_GLOBAL_API_KEY}
      - SERVER_URL=http://localhost:8080
      - DATABASE_ENABLED=true
      - DATABASE_PROVIDER=postgresql
      - DATABASE_CONNECTION_URI=postgresql://user:pass@host:5432/evolution
    volumes:
      - evolution_instances:/evolution/instances
volumes:
  evolution_instances:
```

## Modelo multi-número

### Mapeo: Business ↔ Instancia Evolution

```
Business.id=1, instance_name="barberia-latino", instance_apikey="abc123"
Business.id=2, instance_name="barberia-chapinero", instance_apikey="def456"
```

Cada `Business` tiene:
- `instance_name`: nombre de la instancia en Evolution (único)
- `instance_apikey`: API key de esa instancia (encriptada, solo aplica para `WHATSAPP-BAILEYS`)

El flujo de routing:
1. Webhook recibe `{"instance": "barberia-latino", ...}`
2. `BusinessRepository.get_by_instance_name("barberia-latino")` → `business_id=1`
3. `ConversationService(db, "barberia-latino", business_id=1, apikey="abc123")`
4. Handlers usan `instance_name` + `apikey` para enviar respuestas

**Ventaja sobre Meta**: Con Evolution, el routing es directo — el `instance` name viene en el payload. Con Meta, teníamos que buscar por `phone_number_id` en la BD cada vez.

### Creación programática de instancias

Cuando se crea un nuevo `Business`, el sistema DEBERÍA crear automáticamente la instancia en Evolution:

```python
# En BusinessRepository.create() o en un servicio dedicado
POST {evolution_url}/instance/create
Headers: apikey: {global_api_key}
Body: {
  "instanceName": f"biz-{business.id}",
  "integration": "WHATSAPP-BAILEYS",
  "qrcode": true,
  "webhook": {
    "url": "https://miapp.com/api/v1/webhook",
    "events": ["MESSAGES_UPSERT"],
    "enabled": true
  }
}
# Guardar instance_name + instance_apikey en el Business
```

## Riesgos

### Riesgo 1: Send List en staging — posible inestabilidad
- **Severidad**: ALTA
- **Mitigación**: Probar exhaustivamente Send List en entorno dev antes de migrar producción. Tener un plan B (texto con menú numérico como fallback).

### Riesgo 2: Desconexión de instancias Evolution
- **Severidad**: MEDIA
- **Mitigación**: Evolution tiene reconexión automática. Configurar health check que monitoree `GET /instance/connectionState/{instance}`. Agregar webhook `CONNECTION_UPDATE` para detectar desconexiones.

### Riesgo 3: Rate limiting de WhatsApp Web (~50-80 msgs/min)
- **Severidad**: MEDIA
- **Mitigación**: Implementar cola de mensajes con throttling si la carga supera el límite. Para el MVP actual, el volumen es bajo y no debería ser problema.

### Riesgo 4: Dependencia de Docker + PostgreSQL para Evolution
- **Severidad**: BAJA
- **Mitigación**: Evolution puede correr sin PostgreSQL (en memoria), pero se pierden las instancias al reiniciar. Para producción, PostgreSQL es necesario. El proyecto ya usa PostgreSQL (Neon/Supabase), así que el overhead es mínimo.

### Riesgo 5: Cambio de UX — List vs Buttons
- **Severidad**: MEDIA
- **Mitigación**: El List es funcionalmente equivalente, pero la UX es diferente (un toque extra para abrir la lista). Comunicar el cambio anticipadamente. El beneficio de permitir más de 3 opciones compensa la diferencia de UX.

## Viabilidad

**VIABLE con condiciones.** La migración es técnicamente factible, PERO requiere:

1. **Rediseño completo de la capa de mensajería interactiva**: migrar de `send_interactive_button` a `send_list` en todos los handlers (~35+ sitios de llamada)
2. **Cambio de formato de webhook**: reescribir el parser de payload entrante
3. **Migración de BD**: renombrar columna `phone_number_id` y agregar `instance_apikey`
4. **Infraestructura nueva**: Docker para Evolution API (+ PostgreSQL para persistencia de instancias)
5. **Provisionamiento de instancias**: crear lógica para dar de alta cada negocio como instancia en Evolution (QR code scanning inicial)

No hay bloqueantes absolutos. El principal tradeoff es la discontinuación de botones nativos → migración a List.

## Complejidad estimada: **L (Large)**

| Área | Complejidad |
|------|-------------|
| `whatsapp_service.py` (reescritura) | M |
| `webhook.py` (reescritura parser) | M |
| Handlers (35+ sitios de llamada) | L |
| Migración BD (Alembic) | S |
| Config/scripts | S |
| Tests (reescritura fixtures + payloads) | M |
| Infraestructura (Docker compose) | S |
| Creación programática de instancias | M |

## Recomendación

**Proceder con SDD.** La migración es viable y tiene beneficios claros:
- Eliminación de dependencia de Meta Cloud API y sus restricciones
- Sin costo por conversación (solo hosting)
- Multi-número sin límites de WABA
- Control total sobre la infraestructura

El SDD debe planearse en fases:
1. **Fase 0**: Infraestructura — Docker compose, variables de entorno, health checks
2. **Fase 1**: Capa de envío — `whatsapp_service.py` con soporte dual (Meta + Evolution) para migración gradual
3. **Fase 2**: Capa de recepción — `webhook.py` con detección de formato (Meta vs Evolution)
4. **Fase 3**: Migración de handlers — `send_interactive_button` → `send_list` en todos los handlers
5. **Fase 4**: Migración de BD + scripts + cleanup de código legacy Meta
6. **Fase 5**: Creación programática de instancias + onboarding de negocios
