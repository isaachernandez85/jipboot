"""
Funciones de utilidad para SOPRIM BOT.
Contiene helpers y utilidades comunes usadas en diferentes partes del proyecto.
"""
import logging
import re
import json
import os
from datetime import datetime

# Configurar logging
logger = logging.getLogger(__name__)

def extract_phone_number(phone_with_prefix):
    """
    Extrae un número de teléfono limpio eliminando caracteres no numéricos.
    
    Args:
        phone_with_prefix (str): Número de teléfono posiblemente con formato
        
    Returns:
        str: Número de teléfono limpio
    """
    if not phone_with_prefix:
        return None
    
    # Eliminar todos los caracteres no numéricos
    clean_number = re.sub(r'\D', '', phone_with_prefix)
    
    # Si el número comienza con un código de país, asegurarse de que está en formato correcto
    if clean_number.startswith('52'):
        # Número mexicano, asegurar que tiene el formato +52...
        return f"+{clean_number}"
    elif not clean_number.startswith('+'):
        # Agregar el + si no lo tiene
        return f"+{clean_number}"
    return clean_number

def normalize_product_name(product_name):
    """
    Normaliza el nombre de un producto para búsquedas más consistentes.
    
    Args:
        product_name (str): Nombre del producto a normalizar
        
    Returns:
        str: Nombre del producto normalizado
    """
    if not product_name:
        return ""
    
    # Convertir a minúsculas
    normalized = product_name.lower()
    
    # Eliminar artículos y palabras comunes al inicio
    words_to_remove = ["el ", "la ", "los ", "las ", "un ", "una ", "unos ", "unas ", "de ", "del "]
    for word in words_to_remove:
        if normalized.startswith(word):
            normalized = normalized[len(word):]
    
    # Eliminar caracteres especiales y espacios múltiples
    normalized = re.sub(r'[^\w\s]', ' ', normalized)
    normalized = re.sub(r'\s+', ' ', normalized).strip()
    
    return normalized

def log_to_file(message, level="INFO", log_file="bot_activity.log"):
    """
    Registra un mensaje en un archivo de log.
    
    Args:
        message (str): Mensaje a registrar
        level (str): Nivel de log (INFO, WARNING, ERROR, etc.)
        log_file (str): Ruta al archivo de log
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"[{timestamp}] [{level}] {message}\n"
    
    try:
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(log_entry)
    except Exception as e:
        logger.error(f"Error escribiendo en archivo de log: {e}")

def save_conversation(user_id, message, response, metadata=None):
    """
    Guarda una conversación para análisis futuro.
    
    Args:
        user_id (str): Identificador del usuario
        message (str): Mensaje del usuario
        response (str): Respuesta del bot
        metadata (dict, optional): Metadatos adicionales
    """
    if metadata is None:
        metadata = {}
    
    conversation_dir = "conversations"
    os.makedirs(conversation_dir, exist_ok=True)
    
    # Crear un ID único para el archivo
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{conversation_dir}/conversation_{user_id}_{timestamp}.json"
    
    conversation_data = {
        "user_id": user_id,
        "timestamp": datetime.now().isoformat(),
        "message": message,
        "response": response,
        "metadata": metadata
    }
    
    try:
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(conversation_data, f, ensure_ascii=False, indent=2)
        logger.info(f"Conversación guardada en {filename}")
    except Exception as e:
        logger.error(f"Error guardando conversación: {e}")

def is_medicine_query(message):
    """
    Determina si un mensaje es una consulta sobre medicamentos.
    
    Args:
        message (str): Mensaje a analizar
        
    Returns:
        bool: True si es una consulta sobre medicamentos, False en caso contrario
    """
    message_lower = message.lower()
    
    # Lista de términos relacionados con medicamentos
    medicine_terms = [
        "medicina", "medicamento", "pastilla", "tableta", "jarabe", "comprimido",
        "cápsula", "inyección", "antibiótico", "analgésico", "antinflamatorio",
        "paracetamol", "ibuprofeno", "aspirina", "naproxeno", "omeprazol",
        "loratadina", "cetirizina", "amoxicilina", "azitromicina", "dosis",
        "receta", "prescripción", "farmacia", "farmacéutico", "droga", "remedio"
    ]
    
    # Patrones que indican una consulta sobre medicamentos
    medicine_patterns = [
        r"para (el|la) dolor",
        r"para (el|la|los|las) (\w+)",
        r"tengo (\w+) y necesito",
        r"me duele (la|el) (\w+)",
        r"estoy enfermo",
        r"tengo gripe",
        r"tengo fiebre"
    ]
    
    # Verificar si contiene términos de medicamentos
    for term in medicine_terms:
        if term in message_lower:
            return True
    
    # Verificar si coincide con patrones de consulta sobre medicamentos
    for pattern in medicine_patterns:
        if re.search(pattern, message_lower):
            return True
    
    return False

def format_whatsapp_message(text):
    """
    Formatea un mensaje para WhatsApp, asegurando que no exceda límites y esté bien formateado.
    
    Args:
        text (str): Texto a formatear
        
    Returns:
        str: Texto formateado para WhatsApp
    """
    # WhatsApp tiene un límite aproximado de 4096 caracteres por mensaje
    max_length = 4000
    
    if len(text) > max_length:
        # Truncar el mensaje y añadir indicador de continuación
        text = text[:max_length] + "... (mensaje truncado)"
    
    return text