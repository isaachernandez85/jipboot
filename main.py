import os
import logging
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, PlainTextResponse
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

# Importar el manejador de mensajes
from handlers.message_handler import MessageHandler

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="SOPRIM BOT API",
    description="API para el chatbot de farmacia SOPRIM BOT"
)

# Token de verificación para webhook de WhatsApp
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", "soprim123")

# Inicializar el manejador de mensajes
message_handler = MessageHandler()


@app.get("/webhook")
async def verify(request: Request):
    """
    Endpoint para verificar el webhook con Meta/WhatsApp.
    Esta función es llamada cuando Facebook/Meta intenta verificar el webhook.
    """
    args = dict(request.query_params)
    if args.get("hub.mode") == "subscribe" and args.get("hub.verify_token") == VERIFY_TOKEN:
        logger.info("Webhook verificado correctamente")
        return PlainTextResponse(content=args.get("hub.challenge"), status_code=200)
    logger.warning("Intento de verificación no autorizado")
    return PlainTextResponse(content="Unauthorized", status_code=403)


@app.post("/webhook")
async def webhook(request: Request):
    """
    Endpoint principal para recibir mensajes de WhatsApp desde Twilio.
    """
    try:
        # Leer datos form-urlencoded en lugar de JSON
        form = await request.form()
        logger.info(f"Mensaje recibido (form): {form}")

        # Extraer texto y remitente
        msg_text = form.get("Body", "")
        phone_number = form.get("From", "")
        
        # ACTUALIZADO: Mejorar la detección de imágenes
        num_media = int(form.get("NumMedia", "0"))
        media_urls = []
        
        if num_media > 0:
            logger.info(f"Mensaje contiene {num_media} elementos multimedia")
            # Recopilar URLs de las imágenes
            for i in range(num_media):
                media_url = form.get(f"MediaUrl{i}")
                media_type = form.get(f"MediaContentType{i}")
                
                if media_url and media_type and "image" in media_type:
                    media_urls.append(media_url)
                    logger.info(f"Imagen recibida: {media_url}")

        logger.info(f"Procesando mensaje: '{msg_text}' de {phone_number} con {len(media_urls)} imágenes")

        # Llamar a tu lógica modificada para incluir procesamiento de imágenes
        result = await message_handler.procesar_mensaje(msg_text, phone_number, media_urls)
        logger.info(f"Resultado del procesamiento: {result.get('message_type')}")

        # Twilio solo necesita un 200 OK
        return JSONResponse(content={"status": "processed"}, status_code=200)

    except Exception as e:
        logger.error(f"Error procesando webhook: {e}")
        # Imprimir el traceback completo para depuración
        import traceback
        logger.error(traceback.format_exc())
        # Devuelve 200 para que Twilio no reintente
        return JSONResponse(content={"status": "error", "message": str(e)}, status_code=200)

@app.get("/")
async def root():
    """
    Endpoint raíz que confirma que el servicio está funcionando.
    """
    return {"message": "SOPRIM BOT está activo 🧠", "version": "1.0"}


@app.get("/health")
async def health_check():
    """
    Endpoint para verificar la salud del servicio.
    Útil para monitoreo en Cloud Run.
    """
    return {"status": "healthy"}


@app.post("/test")
async def test_message(request: Request):
    """
    Endpoint para probar el bot con un mensaje simulado.
    Útil para depuración y pruebas.
    """
    try:
        data = await request.json()
        message = data.get("message", "")
        phone = data.get("phone", "+5212345678901")  # Número por defecto

        if not message:
            return JSONResponse(
                content={"status": "error", "message": "No se proporcionó un mensaje"},
                status_code=400
            )

        # Procesar el mensaje
        result = await message_handler.procesar_mensaje(message, phone)

        # Devolver el resultado
        return JSONResponse(
            content={
                "status": "success",
                "message_type": result.get("message_type"),
                "response": result.get("respuesta", "Sin respuesta")
            },
            status_code=200
        )
    except Exception as e:
        logger.error(f"Error en test_message: {e}")
        return JSONResponse(
            content={"status": "error", "message": str(e)},
            status_code=500
        )


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", 8080))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
