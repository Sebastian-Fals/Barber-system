# Guía Completa: Sistema de Citas (WhatsApp + Google Calendar)

Esta guía te ayudará a desplegar el sistema usando tecnologías modernas y robustas: **FastAPI, WhatsApp API, Google Calendar y PostgreSQL (Neon)**.

---

## 🛠️ Parte 1: Preparar tu Entorno

### 1. Instalar Python
Si no lo tienes:
1.  Descarga Python desde [python.org](https://www.python.org/downloads/).
2.  **IMPORTANTE**: Marca la casilla "Add Python to PATH" antes de instalar.

### 2. Instalar Librerías
Abre la terminal en la carpeta del proyecto y ejecuta:
```bash
pip install -r requirements.txt
```

---

## ☁️ Parte 2: Base de Datos (Neon PostgreSQL)

Ya no usamos archivos locales (`.db`) porque dan problemas. Usaremos **Neon** (gratis y en la nube).

1.  Ve a [neon.tech](https://neon.tech) y crea una cuenta.
2.  Crea un **Project** nuevo.
3.  Copia la **Connection String** que te dan. Se ve así:
    `postgres://usuario:password@hosting.../neondb`

---

## 🤖 Parte 3: Configurar Google y Meta

### Google Calendar (Service Account)
1.  Ve a [Google Cloud Console](https://console.cloud.google.com/).
2.  Crea un proyecto y habilita la **Google Calendar API**.
3.  Crea una **Service Account**, genera una **Key (JSON)** y descárgala como `credentials.json` en la carpeta del proyecto.
4.  Comparte tu calendario personal con el **email** del servicio (ej: `bot@...iam.gserviceaccount.com`). Dale permisos de "Hacer cambios en eventos".

### WhatsApp (Meta Developers)
1.  Crea una App en [Meta Developers](https://developers.facebook.com/).
2.  Obtén tu **Token** y tu **Phone Number ID**.

---

## 🚀 Parte 4: Configuración Final (.env)

El archivo `.env` es el corazón del sistema.

1.  Copia el archivo de ejemplo:
    ```bash
    cp .env.example .env
    ```
    *(O simplemente crea un archivo `.env` nuevo)*.

2.  Rellena tus datos:
    ```ini
    # Base de datos (Neon)
    DATABASE_URL="postgresql://... (La que copiaste de Neon)"

    # WhatsApp
    WHATSAPP_API_TOKEN="EAAG..."
    WHATSAPP_VERIFY_TOKEN="citas123"

    # Google
    GOOGLE_APPLICATION_CREDENTIALS="credentials.json"
    
    # Webhook (Tu URL pública, ej: Ngrok)
    WEBHOOK_PUBLIC_URL="https://tudominio.ngrok-free.app/api/v1/google-webhook"
    ```

---

## ⚡ Parte 5: Iniciar el Sistema

### 1. Inicializar la Base de Datos
⚠️ **Advertencia**: Esto borrará cualquier dato previo en la DB y creará el negocio y barbero por defecto.
```bash
python reset_db.py
```

### 2. Arrancar el Servidor
```bash
uvicorn app.main:app --reload
```
Verás logs indicando que el Webhook de Google se ha suscrito correctamente.

### 3. Exponer a Internet (Ngrok/Cloudflared)
Para que WhatsApp y Google te envíen notificaciones, tu PC debe ser accesible:
```bash
ngrok http 8000
```
Copia la URL HTTPS que te da Ngrok y ponla en tu `.env` (variable `WEBHOOK_PUBLIC_URL`) y en la configuración de WhatsApp Developers.

---

## ✅ Verificación
1.  Envía un mensaje a tu bot.
2.  Debería responder el menú.
3.  Agenda una cita -> Verás que aparece en tu Google Calendar al instante.
4.  Crea un evento en tu Google Calendar -> Verás que la base de datos se actualiza (Webhooks).
