import json
import os
from typing import Any, Dict


class I18nService:
    def __init__(self, default_locale: str = "es"):
        self.default_locale = default_locale
        self.locales: Dict[str, Dict[str, str]] = {}
        self._load_locales()

    def _load_locales(self):
        # Determine path relative to this file
        base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        locales_dir = os.path.join(base_path, "locales")

        if not os.path.exists(locales_dir):
            return

        for filename in os.listdir(locales_dir):
            if filename.endswith(".json"):
                lang = filename.split(".")[0]
                try:
                    with open(os.path.join(locales_dir, filename), "r", encoding="utf-8") as f:
                        self.locales[lang] = json.load(f)
                except Exception as e:
                    print(f"Error loading locale {filename}: {e}")

    def get(self, key: str, **kwargs: Any) -> str:
        """
        Retrieve a message by key and format it with kwargs.
        If key not found, returns the key itself.
        """
        # Default to Spanish for now
        messages = self.locales.get(self.default_locale, {})
        msg_template = messages.get(key, key)

        try:
            return msg_template.format(**kwargs)
        except KeyError:
            return msg_template  # Return unformatted if keys missing


# Global instance
message_loader = I18nService()
