from google import genai
from google.genai import types
import json
from app.core.config import settings
import datetime
from app.core.logging_config import logger

class LLMService:
    def __init__(self):
        if settings.GOOGLE_API_KEY:
            self.client = genai.Client(api_key=settings.GOOGLE_API_KEY)
            self.model_name = 'gemini-2.0-flash-lite'
        else:
            logger.warning("WARNING: GOOGLE_API_KEY not set. LLM features will fail.")
            self.client = None

    def analyze_message(self, message_body: str, context: dict):
        """
        Analyzes the incoming message to determine intent and extract entities.
        """
        if not self.client:
            return {"intent": "ERROR", "reply": "Error de configuración de IA."}

        prompt = f"""
        act as the receptionist assistant for a barbershop called {context.get('business_name')}.
        Current Date: {context.get('today')} ({context.get('day_name')}).
        Available Barbers: {', '.join(context.get('barbers', []))}.
        
        User Message: "{message_body}"
        Current State: {context.get('current_state')}
        
        Conversation History (Last 5 messages):
        {json.dumps(context.get('history', []), ensure_ascii=False)}
        
        Your goal is to extract structured data to help the system process the request.
        
        JSON SCHEMA:
        {{
            "intent": "BOOK_APPOINTMENT" | "CANCEL_APPOINTMENT" | "RESCHEDULE" | "CHITCHAT" | "UNKNOWN" | "PROVIDE_NAME" | "CONFIRM_APPOINTMENT",
            "extracted": {{
                "barber_name": "string or null",
                "date": "YYYY-MM-DD or null",
                "time": "HH:MM (24h) or null",
                "time_period": "morning" | "afternoon" | "evening" | null,
                "customer_name": "string or null"
            }},
            "reply": "A friendly, natural language response in Spanish. keep it short (<30 words). If you need more info (like date or barber), ask for it here."
        }}
        
        RULES:
        1. If user says "Agendar con Alejandro", intent is BOOK_APPOINTMENT, barber_name="Alejandro".
        2. If user provides a date like "Mañana", calculate it based on Current Date.
        3. If provided date is "El viernes", calculate the NEXT Friday.
        4. If user says "Hola", intent is CHITCHAT.
        5. If user gives their name (e.g. in ASK_NAME state), intent is PROVIDE_NAME.
        6. If user says "Si", "Confirmar", "Esta bien", "Dale" AND Current State is CONFIRM_BOOKING, intent is CONFIRM_APPOINTMENT.
        7. If user ONLY specifies time (e.g. "a las 4", "en la tarde") and a Date was already discussed in history, KEEP THE SAME DATE (do not default to Today). Output date=null in this case so system keeps previous value.
        8. If user says "en la tarde", set time_period="afternoon". If "en la mañana", time_period="morning".
        9. If user says "Gracias" or "Adios", intent is CHITCHAT, but make the reply a closing statement.
        10. Always output valid JSON only. Do not add markdown backticks.
        """
        
        try:
            # logger.debug(f"LLM Prompt: {prompt}") # Uncomment for verbose debugging
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json"
                )
            )
            return json.loads(response.text)
        except Exception as e:
            logger.error(f"LLM Error: {e}", exc_info=True)
            
            # Robust 429 Check
            is_429 = False
            if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e): is_429 = True
            if hasattr(e, "code") and e.code == 429: is_429 = True
            if hasattr(e, "status") and str(e.status) == "RESOURCE_EXHAUSTED": is_429 = True
            
            if is_429:
                 return {"intent": "FALLBACK", "reply": "", "extracted": {}}

            return {
                "intent": "UNKNOWN", 
                "reply": "Tuve un problema entendiéndote. ¿Podrías repetir?",
                "extracted": {}
            }

llm_service = LLMService()
