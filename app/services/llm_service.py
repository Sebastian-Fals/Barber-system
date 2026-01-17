import datetime
import json

import yaml  # Moved to top level
from google import genai
from google.genai import types

from app.core.config import settings
from app.core.logging_config import logger


class LLMService:
    def __init__(self):
        if settings.GOOGLE_API_KEY:
            self.client = genai.Client(api_key=settings.GOOGLE_API_KEY)
            self.model_name = "gemini-2.0-flash-lite"
        else:
            logger.warning("WARNING: GOOGLE_API_KEY not set. LLM features will fail.")
            self.client = None

    def analyze_message(self, message_body: str, context: dict):
        """
        Analyzes the incoming message to determine intent and extract entities.
        """
        if not self.client:
            return {"intent": "ERROR", "reply": "Error de configuración de IA."}

        try:
            with open("app/core/prompts.yaml", "r", encoding="utf-8") as f:
                prompts = yaml.safe_load(f)

            template = prompts.get("system_prompt", "")

            # Use safe formatting or manual replacement to handle checking for braces in the yaml if needed.
            # But here we formatted the yaml to leverage simple f-string style replacement manually or using .format()
            # However, the yaml contains JSON schema braces {{ }}, so we need to be careful.
            # The simplest way given the code structure is to verify the template works.

            # Replacing placeholders. Using replace() is safer than format() given the JSON schema braces.
            prompt = (
                template.replace("{business_name}", str(context.get("business_name")))
                .replace("{today}", str(context.get("today")))
                .replace("{day_name}", str(context.get("day_name")))
                .replace("{barbers}", ", ".join(context.get("barbers", [])))
                .replace("{message_body}", message_body)
                .replace("{customer_name}", str(context.get("customer_name") or "No identificado"))
                .replace("{current_state}", str(context.get("current_state")))
                .replace("{history}", json.dumps(context.get("history", []), ensure_ascii=False))
            )

        except Exception as e:
            logger.error(f"Error loading prompt: {e}")
            return {"intent": "ERROR", "reply": "Error interno de configuración."}

        try:
            # logger.debug(f"LLM Prompt: {prompt}") # Uncomment for verbose debugging
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(response_mime_type="application/json"),
            )
            return json.loads(response.text)
        except Exception as e:
            logger.error(f"LLM Error: {e}", exc_info=True)

            # Robust 429 Check
            is_429 = False
            if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                is_429 = True
            if hasattr(e, "code") and e.code == 429:
                is_429 = True
            if hasattr(e, "status") and str(e.status) == "RESOURCE_EXHAUSTED":
                is_429 = True

            if is_429:
                return {"intent": "FALLBACK", "reply": "", "extracted": {}}

            return {"intent": "UNKNOWN", "reply": "Tuve un problema entendiéndote. ¿Podrías repetir?", "extracted": {}}


llm_service = LLMService()
