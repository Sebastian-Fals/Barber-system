# Guía Completa: Sistema de Citas (WhatsApp + Google Calendar)

Esta guía está diseñada para configurar el sistema desde cero, asumiendo que es la primera vez que configuras estas herramientas.

---

## 🛠️ Parte 1: Preparar tu Computadora

Antes de empezar, necesitamos instalar las herramientas básicas.

### 1. Instalar Python
Si no lo tienes:
1.  Descarga Python desde [python.org](https://www.python.org/downloads/).
2.  Al instalar, **asegúrate de marcar la casilla "Add Python to PATH"** antes de dar clic en Install.

### 2. Abrir la Terminal en la Carpeta del Proyecto
1.  Ve a la carpeta de tu proyecto (`sistema-citas`) en el explorador de archivos y entra en ella.
2.  Haz clic derecho en un espacio vacío y selecciona "Open available terminal" o abre VS Code y usa `Ctrl + ñ` (o `Ctrl + ` ` `).

### 3. Instalar las librerías necesarias
Escribe este comando en la terminal y presiona Enter:
```bash
pip install -r requirements.txt
```
*Si ves errores de permisos, prueba abrir la terminal como Administrador.*

### 4. Instalar Ngrok (Para conectar tu PC a Internet)
WhatsApp necesita "ver" tu computadora para enviarte mensajes. Usaremos Ngrok.
1.  Ve a [ngrok.com](https://ngrok.com/download) y regístrate (es gratis).
2.  Descarga el archivo ZIP para Windows.
3.  Descomprime el archivo (tendrás un `ngrok.exe`).
4.  Mueve ese `ngrok.exe` dentro de la carpeta de tu proyecto.
5.  En la web de Ngrok, copia tu "Authtoken" (te aparecerá en el dashboard) y execútalo en la terminal:
    ```bash
    ngrok config add-authtoken TU_TOKEN_AQUI
    ```

---

## 🤖 Parte 2: Configurar el "Robot" de Google Calendar

Necesitamos crear una cuenta especial (Service Account) para que el programa pueda manipular calendarios.

### 1. Crear el Proyecto en Google Cloud
1.  Entra a [Google Cloud Console](https://console.cloud.google.com/).
2.  Arriba a la izquierda, haz clic en el selector de proyectos y luego en **"New Project"**.
3.  Ponle nombre (ej: `SistemaCitas`) y dale a **Create**.
4.  Espera un momento y **selecciona el proyecto** que acabas de crear.

### 2. Activar la API de Calendar
1.  En la barra de búsqueda de arriba, escribe `Google Calendar API`.
2.  Haz clic en el resultado y luego en el botón azul **ENABLE** (Habilitar).

### 3. Crear credenciales (Service Account)
1.  Ve al menú (tres rayas) -> **IAM & Admin** -> **Service Accounts**.
2.  Clic en **+ CREATE SERVICE ACCOUNT**.
    - **Name**: `bot-citas`.
    - Dale a **Create and Continue**.
3.  En "Select a role", busca y selecciona **Owner** (Propietario) para facilitar las cosas (o `Editor`). Dale a **Continue** y luego **Done**.

### 4. Descargar la Llave (JSON)
1.  Verás tu nueva cuenta en la lista (ej: `bot-citas@....iam.gserviceaccount.com`). Haz clic en los tres puntos a la derecha -> **Manage keys**.
2.  Clic en **ADD KEY** -> **Create new key**.
3.  Selecciona **JSON** y dale a **Create**.
4.  Se descargará un archivo. **Cópialo a la carpeta de tu proyecto** y renómbralo a `credentials.json`.
5.  **IMPORTANTE**: Copia el **email** de esa cuenta (ej: `bot-citas@tu-proyecto...`) que sale en la consola. Lo necesitarás ahora.

### 5. Dar permiso al Robot en TU Calendar
1.  Abre tu [Google Calendar](https://calendar.google.com/) personal.
2.  En la izquierda, busca tu calendario ("Sebastian Fals"), clic en los 3 puntos -> **Configuración y uso compartido**.
3.  Baja hasta "Compartir con personas específicas".
4.  Clic en **Añadir personas**.
5.  Pega el email del robot (`bot-citas@...`).
6.  En permisos, elige **"Hacer cambios en eventos"**. ¡Crucial!
7.  Dale a Enviar.
8.  Más abajo, busca "ID del calendario" (suele ser tu email). Cópialo.

---

## 💬 Parte 3: Configurar WhatsApp (Meta)

### 1. Crear la App en Meta
1.  Entra a [developers.facebook.com](https://developers.facebook.com/) e inicia sesión.
2.  Clic en **Mis Apps** -> **Crear App**.
3.  Elige **"Other"** (Otro) -> Next -> **Business** (Negocio).
4.  Ponle nombre (ej: `CitasApp`) y crea la app.

### 2. Configurar WhatsApp
1.  En el panel de la izquierda (o busca "Add products"), busca **WhatsApp** y dale a **Set up**.
2.  Te llevará a "Getting Started". Aquí verás:
    - **Temporary Access Token**: Cópialo.
    - **Phone Number ID**: Cópialo.
    - **Test Number**: Tu número de prueba.

### 3. Añadir tu número real
1.  En esa misma página, baja a "To" (Para).
2.  Añade tu número de teléfono personal para poder recibir los mensajes de prueba (te enviarán un código de verificación).

---

## 🚀 Parte 4: Conectar Todo

### 1. Configurar tus Claves (.env)
1.  En tu carpeta de proyecto, tienes un archivo `.env.example`.
2.  Haz una copia de ese archivo y llámala simplemente `.env`.
3.  Abre `.env` con el Bloc de Notas o VS Code y rellena los datos:
    ```ini
    WHATSAPP_API_TOKEN="Pega aqui tu Temporary Access Token de Meta"
    WHATSAPP_VERIFY_TOKEN="citas123"  <-- Puedes dejar este o inventar uno
    GOOGLE_APPLICATION_CREDENTIALS="credentials.json"
    ```
4.  Guarda el archivo.

### 2. Inicializar la Base de Datos
En la terminal, escribe:
```bash
python init_db.py
```
Debería decir "Database initialized successfully!".

### 3. Registrar el Negocio (Manual por ahora)
Como no tenemos pantalla de administración, haremos un truco rápido para registrar tu negocio.
Crea un archivo nuevo `crear_negocio.py` y pega esto:
```python
from app.core.database import SessionLocal
from app.models.models import Business

db = SessionLocal()
# REEMPLAZA ESTOS DATOS:
mi_negocio = Business(
    name="Peluquería Sebastian",
    phone_number_id="123456789", # <--- PEGA AQUÍ EL 'Phone Number ID' DE META
    calendar_id="pega_tu_email@gmail.com" # <--- PEGA AQUÍ EL ID DE TU CALENDARIO
)
db.add(mi_negocio)
db.commit()
print("Negocio creado!")
```
Ejecútalo: `python crear_negocio.py`

### 4. Arrancar el Servidor
En la terminal:
```bash
uvicorn app.main:app --reload
```
Verás muchas letras verdes/blancas. No cierres esta ventana.

---

## 🌐 Parte 5: Abrir al Mundo

### 1. Activar Ngrok
Abre **OTRA** ventana de terminal (sin cerrar la anterior).
Escribe:
```bash
ngrok http 8000
```
Verás una pantalla con una linea que dice Forwarding: `https://xxxx-xxxx.ngrok-free.app`.
**Copia esa dirección HTTPS.**

### 2. Conectar WhatsApp al Servidor
1.  Vuelve a [developers.facebook.com](https://developers.facebook.com/) -> WhatsApp -> **Configuration**.
2.  Busca el recuadro **Webhook** y dale a **Edit**.
3.  **Callback URL**: Pega la dirección de Ngrok y añadele `/api/v1/webhook` al final.
    - Ejemplo: `https://xxxx-xxxx.ngrok-free.app/api/v1/webhook`
4.  **Verify Token**: Escribe lo que pusiste en el .env (`citas123`).
5.  Clic en **Verify and Save**.

### 3. Suscribirse a Mensajes
1.  Debajo de Webhook, verás **"Webhook fields"**. Dale a **Manage**.
2.  Busca `messages` y dale a **Subscribe** (Columna v16.0 o mayor).

---

## 🎉 ¡Prueba Final!
1.  Toma tu celular.
2.  Abre WhatsApp y busca el chat con el número de prueba de Meta (el que te dio en el panel).
3.  Escribe "Hola".
4.  Si todo salió bien:
    - En la terminal de Python (`uvicorn`) verás el mensaje llegando.
    - El bot te responderá en WhatsApp automáticamente.
