import requests

from app.core.config import settings


class WhatsAppService:
    """Sends WhatsApp messages via self-hosted Evolution API (Baileys engine)."""

    def __init__(self):
        self.base_url = settings.EVOLUTION_API_URL.rstrip("/")

    def send_message(self, instance_name: str, apikey: str, to: str, body: str):
        """
        Sends a text message via Evolution API.
        POST /message/sendText/{instance_name}
        """
        url = f"{self.base_url}/message/sendText/{instance_name}"
        headers = {
            "apikey": apikey,
            "Content-Type": "application/json",
        }
        data = {
            "number": to,
            "text": body,
        }

        try:
            response = requests.post(url, headers=headers, json=data, timeout=15)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error sending WhatsApp message: {e}")
            if "response" in locals() and response is not None:
                print(f"Response: {response.text}")
            return None

    def send_list(
        self,
        instance_name: str,
        apikey: str,
        to: str,
        title: str,
        description: str,
        button_text: str,
        footer_text: str,
        rows: list,
    ):
        """
        Sends an interactive list message via Evolution API.
        POST /message/sendList/{instance_name}

        rows format: [{"title": "Option", "description": "...", "rowId": "opt_1"}, ...]
        """
        url = f"{self.base_url}/message/sendList/{instance_name}"
        headers = {
            "apikey": apikey,
            "Content-Type": "application/json",
        }

        data = {
            "number": to,
            "title": title,
            "description": description,
            "buttonText": button_text,
            "footerText": footer_text,
            "sections": [
                {
                    "title": "Opciones",
                    "rows": rows,
                }
            ],
        }

        try:
            response = requests.post(url, headers=headers, json=data, timeout=15)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error sending WhatsApp list: {e}")
            if "response" in locals() and response is not None:
                print(f"Response: {response.text}")
            return None


whatsapp_service = WhatsAppService()
