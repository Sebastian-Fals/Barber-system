import requests
import json
from app.core.config import settings

class WhatsAppService:
    def __init__(self):
        self.base_url = "https://graph.facebook.com/v18.0"
        self.token = settings.WHATSAPP_API_TOKEN

    def send_message(self, phone_number_id: str, to_number: str, message_body: str):
        """
        Sends a text message using the WhatsApp Cloud API.
        """
        url = f"{self.base_url}/{phone_number_id}/messages"
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }
        data = {
            "messaging_product": "whatsapp",
            "to": to_number,
            "type": "text",
            "text": {"body": message_body},
        }

        try:
            response = requests.post(url, headers=headers, json=data)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error sending WhatsApp message: {e}")
            if response:
                print(f"Response: {response.text}")
            return None

    def send_interactive_button(self, phone_number_id: str, to_number: str, body_text: str, buttons: list):
        """
        Sends a message with interactive buttons.
        buttons format: [{"id": "btn1", "title": "Buy Now"}, ...]
        """
        url = f"{self.base_url}/{phone_number_id}/messages"
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }
        
        formatted_buttons = []
        for btn in buttons:
            formatted_buttons.append({
                "type": "reply",
                "reply": {
                    "id": btn["id"],
                    "title": btn["title"]
                }
            })

        data = {
            "messaging_product": "whatsapp",
            "to": to_number,
            "type": "interactive",
            "interactive": {
                "type": "button",
                "body": {"text": body_text},
                "action": {
                    "buttons": formatted_buttons
                }
            }
        }
        
        try:
            response = requests.post(url, headers=headers, json=data)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error sending WhatsApp interactive message: {e}")
            return None

whatsapp_service = WhatsAppService()
