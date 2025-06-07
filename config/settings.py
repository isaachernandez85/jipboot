"""
Archivo de configuración para SOPRIM BOT.
Centraliza todas las claves API y parámetros de configuración.
Ahora adaptado para incluir Google Cloud Vision para OCR.
CORREGIDO: Agregado logger para funciones de margen.
"""
import os
import re
import logging  # ← AGREGADO
from dotenv import load_dotenv

# ✅ CONFIGURAR LOGGING
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)  # ← AGREGADO

# Cargar variables de entorno desde archivo .env si existe
load_dotenv()

# --------------------------------------------------
# Configuración de Gemini (IA)
# --------------------------------------------------
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL   = os.getenv("GEMINI_MODEL", "models/gemini-1.5-pro-latest") 

# ✅ Instrucciones de contexto para Gemini - ACTUALIZADAS
GEMINI_SYSTEM_INSTRUCTIONS = """
Eres SOPRIM BOT, un asistente virtual amigable, servicial y eficiente para INSUMOS JIP.
Tu objetivo principal es ayudar a los usuarios a consultar información comercial sobre productos, como disponibilidad, precios y opciones de entrega.

**Información Importante de INSUMOS JIP:**
* **Nombre de la Empresa:** INSUMOS JIP
* **Dirección:** Baya #503, Col. Arboledas de San José, León, México.
* **Confirmaciones de Pedidos y Recolecciones:** Para confirmar pedidos, programar recolecciones o cualquier detalle relacionado, los usuarios deben contactar a Isaac al +52 1 477 677 5291 ( wa.me/524776775291 o llamada).

**REGLAS CRÍTICAS DE INTERACCIÓN:**
1.  Responde siempre en español, de manera concisa, útil y amigable.
2.  **NUNCA proporciones información médica,** como efectos secundarios, indicaciones, contraindicaciones, dosis o consejos de salud.
3.  **NO te refieras a los artículos como "medicamentos" o "fármacos"; usa siempre el término "productos" o "artículos".**
4.  NO ofrezcas consultas médicas ni farmacéuticas. Si un usuario pregunta sobre uso médico, efectos, o cualquier tema de salud, indica clara y únicamente: "Para información sobre el uso o efectos de este producto, por favor, consulte con su médico."
5.  **NO menciones "receta médica".** Si un producto la requiere, simplemente informa: "Este producto requiere presentar receta para su venta."
6.  Enfócate EXCLUSIVAMENTE en información comercial:
    * Disponibilidad del producto.
    * Precio del producto.
    * Opciones y tiempos de entrega.
    * Cómo confirmar un pedido o solicitar una recolección (proporcionando la dirección y el contacto de Isaac según se requiera).
7.  Mantén un tono estrictamente comercial y de servicio al cliente, nunca clínico o médico.
8.  Si el usuario envía una imagen con texto (ej. una foto de un producto o una lista), procesa la información textual de la imagen como si el usuario la hubiera escrito.
9.  Para emergencias médicas, siempre sugiere: "Si se trata de una emergencia médica, por favor busque atención médica inmediata o llame a los servicios de emergencia."
10. Si el usuario consulta por varios productos en un solo mensaje, amablemente indícale: "Para poder ayudarte mejor y evitar errores, por favor consulta los productos de uno en uno. ¿Cuál te gustaría consultar primero?"
11. Cuando proporciones información de un producto, sé claro sobre el precio y el origen de la información (Ej: "Precio: $XX.XX (Origen: DF)").
12. Si un producto no se encuentra, informa al usuario y pregúntale si desea buscar alternativas o si puede proporcionar más detalles del producto.

**Tu Rol:** Eres un asistente de ventas y servicio al cliente para INSUMOS JIP, no un profesional de la salud. Tu meta es facilitar las transacciones comerciales.
"""

# --------------------------------------------------
# Configuración de Twilio WhatsApp Sandbox
# --------------------------------------------------
TWILIO_ACCOUNT_SID             = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN              = os.getenv("TWILIO_AUTH_TOKEN", "")
TWILIO_WHATSAPP_SANDBOX_NUMBER = os.getenv(
    "TWILIO_WHATSAPP_SANDBOX_NUMBER",
    "whatsapp:+14155238886" 
)

# --------------------------------------------------
# Configuración de Google Cloud Vision (OCR)
# --------------------------------------------------
GOOGLE_CLOUD_VISION_API_KEY = os.getenv("GOOGLE_CLOUD_VISION_API_KEY", "")
GOOGLE_APPLICATION_CREDENTIALS = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "") 

# --------------------------------------------------
# Números permitidos (opcional)
# --------------------------------------------------
ALLOWED_TEST_NUMBERS = [
    "+5214778150806", 
]

# --------------------------------------------------
# Configuración de scraping (si aplica)
# --------------------------------------------------
HEADLESS_BROWSER = os.getenv("HEADLESS_BROWSER", "True").lower() in ("true", "1", "t")

# --------------------------------------------------
# Modo de desarrollo y verificación de webhook
# --------------------------------------------------
DEBUG         = os.getenv("DEBUG", "True").lower() in ("true", "1", "t")
VERIFY_TOKEN  = os.getenv("VERIFY_TOKEN", "soprim123")

# --------------------------------------------------
# 💰 CONFIGURACIÓN DE MÁRGENES DE GANANCIA POR PROVEEDOR
# --------------------------------------------------

# Márgenes de ganancia en porcentaje por proveedor
MARGENES_GANANCIA = {
    "Sufarmed": 45,
    "Difarmer": 45, 
    "NADRO": 13,
    "FANASA": 15,
    "Nadro": 13,  # Variante de NADRO
    "Fanasa": 15, # Variante de FANASA
    "Base Interna": 0,  # Sin margen para productos propios
    "INSUMOS JIP": 0,   # Sin margen para productos propios
    "SOPRIM": 0         # Sin margen para productos propios
}

def extraer_precio_numerico(precio_str):
    """
    Extrae el valor numérico de un precio en formato string.
    
    Args:
        precio_str (str): Precio en formato string (ej: "$120.50", "120,50")
        
    Returns:
        float: Valor numérico del precio o 0.0 si no se puede extraer
    """
    if not precio_str:
        logger.debug(f"💰 [PRECIO] Precio vacío recibido")
        return 0.0
    
    logger.debug(f"💰 [PRECIO] Extrayendo precio numérico de: '{precio_str}'")
    
    # Eliminar símbolos de moneda y espacios
    clean_price = str(precio_str).replace('$', '').replace(' ', '')
    
    # Convertir comas a puntos si es necesario
    if ',' in clean_price and '.' not in clean_price:
        clean_price = clean_price.replace(',', '.')
    elif ',' in clean_price and '.' in clean_price:
        # Formato como "$1,234.56"
        clean_price = clean_price.replace(',', '')
    
    # Extraer el número con regex
    match = re.search(r'(\d+(\.\d+)?)', clean_price)
    
    if match:
        precio_extraido = float(match.group(1))
        logger.debug(f"💰 [PRECIO] Precio extraído: {precio_extraido}")
        return precio_extraido
    else:
        logger.warning(f"💰 [PRECIO] No se pudo extraer precio de: '{precio_str}'")
        return 0.0

def calcular_precio_con_margen(precio_compra, fuente_proveedor):
    """
    Calcula el precio de venta aplicando el margen correspondiente al proveedor.
    FÓRMULA CORRECTA: Margen sobre precio de venta (no sobre costo)
    
    Args:
        precio_compra (float): Precio de compra del producto
        fuente_proveedor (str): Nombre del proveedor/fuente
        
    Returns:
        float: Precio de venta con margen aplicado
    """
    margen = MARGENES_GANANCIA.get(fuente_proveedor, 0)
    
    logger.debug(f"💰 [MARGEN] Calculando margen para {fuente_proveedor}: {margen}%")
    
    # Si no hay margen (Base Interna), devolver precio original
    if margen == 0:
        logger.debug(f"💰 [MARGEN] Sin margen para {fuente_proveedor}, precio final: ${precio_compra:.2f}")
        return precio_compra
    
    # FÓRMULA CORRECTA: Precio_final = Costo / (1 - margen/100)
    # Ejemplo: $100 con 45% margen = $100 / (1 - 0.45) = $100 / 0.55 = $181.82
    precio_venta = precio_compra / (1 - margen / 100)
    
    logger.info(f"💰 [MARGEN] {fuente_proveedor} ({margen}%): ${precio_compra:.2f} → ${precio_venta:.2f}")
    
    return precio_venta

def formatear_precio_mexicano(precio_float):
    """
    Formatea un precio numérico al formato mexicano con símbolo de peso.
    
    Args:
        precio_float (float): Precio numérico
        
    Returns:
        str: Precio formateado (ej: "$1,234.56")
    """
    precio_formateado = f"${precio_float:,.2f}"
    logger.debug(f"💰 [FORMATO] Precio formateado: {precio_formateado}")
    return precio_formateado
