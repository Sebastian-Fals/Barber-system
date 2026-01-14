    def _send_deterministic_fallback(self, customer):
        msg = f"Hola {customer.name or ''}. Para ayudarte, por favor selecciona una opción del menú 👇"
        self._send_welcome_menu(customer)
        # Or specifically send a text message + menu if needed, but reusing welcome menu is safer.
        # whatsapp_service.send_message(self.phone_number_id, customer.phone, msg)
        # Buttons are better.
