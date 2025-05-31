import os
import logging
from twilio.rest import Client

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class WhatsAppService:
    """
    Servicio para enviar mensajes de WhatsApp usando Twilio.
    """

    def __init__(self):
        """
        Inicializa el cliente de Twilio con credenciales de entorno.
        """
        self.account_sid = os.getenv("TWILIO_ACCOUNT_SID")
        self.auth_token = os.getenv("TWILIO_AUTH_TOKEN")
        # El número de sandbox de Twilio debe incluir el prefijo "whatsapp:"
        self.from_number = os.getenv(
            "TWILIO_WHATSAPP_SANDBOX_NUMBER",
            "whatsapp:+14155238886"
        )

        if not all([self.account_sid, self.auth_token]):
            logger.error("Faltan TWILIO_ACCOUNT_SID o TWILIO_AUTH_TOKEN en el entorno")
        else:
            logger.info("Twilio credentials cargadas correctamente")

        self.client = Client(self.account_sid, self.auth_token)
        logger.info(f"Twilio WhatsApp inicializado con número: {self.from_number}")

    def format_phone_number(self, number: str) -> str:
        """
        Elimina el prefijo 'whatsapp:' del número si existe y devuelve
        solo el número en formato internacional.
        
        Args:
            number (str): Número de teléfono, posiblemente con prefijo 'whatsapp:'
            
        Returns:
            str: Número de teléfono sin el prefijo 'whatsapp:'
        """
        if number.startswith("whatsapp:"):
            cleaned_number = number[9:]  # Quitar los primeros 9 caracteres ('whatsapp:')
            logger.info(f"Prefijo 'whatsapp:' eliminado del número: {number} -> {cleaned_number}")
            return cleaned_number
        return number

    def _format_recipient(self, phone_number: str) -> str:
        """
        Asegura que el número venga en formato internacional y
        con el prefijo "whatsapp:" que Twilio requiere.
        """
        # Elimina caracteres no numéricos excepto '+'
        cleaned = ''.join(c for c in phone_number if c.isdigit() or c == '+')
        if not cleaned.startswith('+'):
            cleaned = '+' + cleaned
        return f"whatsapp:{cleaned}"

    def send_text_message(self, recipient: str, message: str) -> dict:
        """
        Envía un mensaje de texto por WhatsApp a través de Twilio.

        Args:
            recipient (str): Número del destinatario (ej. +521234567890)
            message (str): Texto a enviar

        Returns:
            dict: Resultado con estado y SID o error
        """
        try:
            to_number = self._format_recipient(recipient)
            msg = self.client.messages.create(
                from_=self.from_number,
                to=to_number,
                body=message
            )
            logger.info(f"Mensaje enviado a {to_number}. SID: {msg.sid}")
            return {"status": "success", "sid": msg.sid}
        except Exception as e:
            logger.error(f"Error enviando mensaje con Twilio: {e}")
            return {"status": "error", "message": str(e)}

    def send_image_message(self, recipient: str, image_url: str, caption: str = None) -> dict:
        """
        Envía una imagen por WhatsApp a través de Twilio.

        Args:
            recipient (str): Número del destinatario (ej. +521234567890)
            image_url (str): URL de la imagen
            caption (str, optional): Texto adicional

        Returns:
            dict: Resultado con estado y SID o error
        """
        try:
            to_number = self._format_recipient(recipient)
            params = {
                "from_": self.from_number,
                "to": to_number,
                "media_url": [image_url]
            }
            if caption:
                params["body"] = caption

            msg = self.client.messages.create(**params)
            logger.info(f"Imagen enviada a {to_number}. SID: {msg.sid}")
            return {"status": "success", "sid": msg.sid}
        except Exception as e:
            logger.error(f"Error enviando imagen con Twilio: {e}")
            return {"status": "error", "message": str(e)}

    def send_product_response(self, recipient: str, text_response: str, product_info: dict = None) -> dict:
        """
        Envía primero texto y, si existe, una imagen de producto.

        Args:
            recipient (str): Número del destinatario
            text_response (str): Mensaje de texto
            product_info (dict, optional): {
                "nombre": "Producto",
                "imagen": "https://..."
            }

        Returns:
            dict: {"text": {...}, "image": {...}}
        """
        results = {}
        # 1) Enviar texto
        results["text"] = self.send_text_message(recipient, text_response)

        # 2) Si hay imagen y no hubo error
        if product_info and product_info.get("imagen") and results["text"].get("status") == "success":
            image_url = product_info["imagen"]
            caption = f"Producto: {product_info.get('nombre', '')}"
            results["image"] = self.send_image_message(recipient, image_url, caption)

        return results
