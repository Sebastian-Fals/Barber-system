# 💰 Análisis de Costos Operativos

Este documento detalla los costos asociados con la operación del Sistema de Citas, estimados en **Pesos Colombianos (COP)**.

> ⚠️ **Nota**: Los precios dependen de la tasa de cambio del dólar (TRM). Para este cálculo se usa un valor de referencia aproximado de **$3,800 - $4,000 COP por 1 USD**.

---

## 1. WhatsApp Business API (Meta)

Meta cobra por **conversaciones de 24 horas**, no por mensaje individual. Las tarifas varían según quién inicia la charla y el propósito.

### 🆓 Capa Gratuita
*   **1,000 conversaciones de servicio gratuitas** al mes.
*   Conversaciones de servicio (iniciadas por el usuario) son **GRATUITAS** (desde Nov 2024).

### 🏷️ Tarifas Estimadas (2025)

| Tipo de Conversación | Descripción | Costo Aprox (USD) | Costo Aprox (COP) |
| :--- | :--- | :--- | :--- |
| **Servicio** | Cliente escribe ("Hola", "Agendar") | **GRATIS** | **$0** |
| **Utilidad** | Confirmaciones de cita, recordatorios post-transacción | ~$0.0002 | ~$0.8 - $1.0 COP |
| **Marketing** | Promociones enviadas por el negocio | ~$0.0125 | ~$50 COP |
| **Autenticación** | Códigos de verificación (OTPs) | ~$0.0077 | ~$30 COP |

### 🧮 Ejemplo de Costo Mensual
Para una barbería pequeña que atiende 200 citas al mes:

1.  **Agendamiento (Iniciado por usuario)**: 200 conversaciones -> **$0 COP** (Categoría Servicio).
2.  **Recordatorios (Iniciado por negocio)**: 200 utilidades -> 200 * $1 COP = **$200 COP**.
3.  **Promoción Mensual**: Enviar 100 mensajes -> 100 * $50 COP = **$5,000 COP**.

**Total Estimado: ~$5,200 COP / mes.** (Muy económico para operación estándar).

---

## 2. Google Calendar API

Google ofrece una capa gratuita extremadamente generosa para esta API.

*   **Costo**: **$0 (Gratis)** para casi todos los casos de uso estándar.
*   **Límites**: Hasta 1,000,000 de solicitudes por día.
*   El sistema actual difícilmente superará este límite.

---

## 3. Infraestructura (Servidor)

El software debe ejecutarse en algún lugar.

| Opción | Descripción | Costo Estimado |
| :--- | :--- | :--- |
| **PC Local (Actual)** | Tu computadora encendida con Ngrok. | **$0** (Solo electricidad e internet) |
| **VPS (Nube)** | Servidor básico (DigitalOcean, AWS, Linode). | ~$5 - $10 USD/mes (~$40,000 COP) |
| **Render / Railway** | Hosting PaaS (Capa gratuita disponible). | **$0 - $5 USD/mes** |

---

## 4. Base de Datos

| Servicio | Descripción | Costo Estimado |
| :--- | :--- | :--- |
| **Neon Tech** | Postgres Serverless (Capa Gratuita). | **$0** (Hasta 0.5GB almacenamiento) |
| **Render Postgres** | Postgres en Render. | ~$7 USD/mes (Capa más baja) |

---

## 🏁 Resumen Total

Para operar el sistema en su estado actual (PC Local):

*   **Costos Fijos**: $0 COP.
*   **Costos Variables (WhatsApp)**: Aprox. $1 - $50 COP por conversación iniciada por el negocio (recordatorios/promo). Las que inician los clientes son gratis.

**Costo Mensual Esperado: < $10,000 COP** (Para un volumen bajo/medio).
