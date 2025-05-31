"""
Manejador de mensajes para SOPRIM BOT.
Enfoque simplificado para OCR: Envía mensaje guía, procesa el primer ítem detectado
de forma más inteligente por Gemini, y solicita al usuario que envíe los demás ítems de una lista uno por uno.
"""
import logging
import re
import traceback
import time
import asyncio 

from datetime import datetime, timedelta

from services.gemini_service import GeminiService
from services.whatsapp_service import WhatsAppService
from services.scraping_service import ScrapingService 
from services.ocr_service import OCRService 
from services.sheets_service import SheetsService
from services.firestore_service import obtener_historial, guardar_interaccion
from config.settings import ALLOWED_TEST_NUMBERS 

logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class MessageHandler:
    
    def __init__(self):
        logger.info("🚀 Inicializando MessageHandler v3.7 (OCR con Extracción Dirigida por Gemini)")
        self.gemini_service = GeminiService()
        self.whatsapp_service = WhatsAppService()
        self.scraping_service = ScrapingService() 
        self.ocr_service = OCRService() 
        self.sheets_service = SheetsService()
        
        self.MAX_PRODUCTOS_POR_USUARIO_EN_LISTA = 5 
        self.TIMEOUT_POR_PRODUCTO = 120 
        self.THROTTLE_DELAY_SCRAPING = 3 
        
        self.ultimo_scraping_usuario = {}
        self.circuit_breaker_config = {
            "fails": 0, 
            "last_fail_time": None, 
            "is_open": False, 
            "open_duration_seconds": 300,
            "max_fails": 3
        }
        self.mensaje_espera_enviado = {}
        logger.info("✅ MessageHandler v3.7 (OCR con Extracción Dirigida por Gemini) inicializado.")

    def _check_circuit_breaker(self):
        cb = self.circuit_breaker_config
        if cb["is_open"]:
            if cb["last_fail_time"] and (datetime.now() - cb["last_fail_time"]).seconds > cb["open_duration_seconds"]:
                cb["is_open"] = False
                cb["fails"] = 0
                logger.info("🟢 Circuit breaker CERRADO automáticamente después del periodo de enfriamiento.")
                return False
            logger.warning(" CIRCUIT breaker ABIERTO. Rechazando temporalmente la solicitud.")
            return True
        return False

    def _update_circuit_breaker(self, success=True):
        cb = self.circuit_breaker_config
        if success:
            if cb["fails"] > 0:
                 cb["fails"] = max(0, cb["fails"] - 1)
            if cb["fails"] == 0:
                 logger.debug(f"Operación exitosa, fallos reseteados o mantenidos en 0.")
            else:
                 logger.debug(f"Operación exitosa, fallos actuales: {cb['fails']}")
        else:
            cb["fails"] += 1
            cb["last_fail_time"] = datetime.now()
            logger.warning(f"Operación fallida. Fallos acumulados: {cb['fails']}.")
            if cb["fails"] >= cb["max_fails"] and not cb["is_open"]:
                cb["is_open"] = True
                logger.error(f"🔴 Circuit breaker ABIERTO debido a {cb['max_fails']} fallos consecutivos.")
    
    def _can_process_scraping_throttled(self, phone_number_key_clean: str) -> bool:
        now = datetime.now()
        if phone_number_key_clean in self.ultimo_scraping_usuario:
            time_diff_seconds = (now - self.ultimo_scraping_usuario[phone_number_key_clean]).total_seconds()
            if time_diff_seconds < self.THROTTLE_DELAY_SCRAPING:
                logger.info(f"⏱️ Throttling de scraping activo para {phone_number_key_clean}. Esperando {self.THROTTLE_DELAY_SCRAPING - time_diff_seconds:.1f}s")
                return False
        self.ultimo_scraping_usuario[phone_number_key_clean] = now
        return True

    def _generar_mensaje_instrucciones_multiples(self, productos_detectados_lista: list, mensaje_original_usuario: str) -> str:
        num_productos = len(productos_detectados_lista)
        mensaje = f"Detecté que mencionaste varios productos en tu mensaje de texto: '{mensaje_original_usuario}'.\n"
        mensaje += "\nPara darte la información más precisa, ¿podrías decirme cuál de estos te gustaría que consulte primero?\n"
        for i, prod in enumerate(productos_detectados_lista[:3]): 
            mensaje += f" - {prod.strip().capitalize()}\n"
        if num_productos > 3:
            mensaje += f"... y otros más.\n"
        mensaje += "\nEscribe solo el nombre del que quieres ahora, por favor."
        return mensaje

    def _detectar_productos_locales_simples(self, mensaje_texto: str) -> list:
        if not mensaje_texto or len(mensaje_texto) < 3: return []
        mensaje_lower = mensaje_texto.lower()
        productos_clave = [
            "paracetamol", "ibuprofeno", "aspirina", "dualgos", "losartan", "metformina", "tramadol",
            "amoxicilina", "omeprazol", "diclofenaco", "sildenafil", "tadalafil", "clonazepam",
        ]
        detectados = []
        for p_clave in productos_clave:
            if re.search(r'\b' + re.escape(p_clave) + r'\b', mensaje_lower):
                detectados.append(p_clave)
        if detectados: logger.info(f"[Fallback Local] Detección simple encontró: {detectados}")
        return list(set(detectados))

    async def _enviar_mensaje_espera_si_necesario(self, phone_number: str, phone_number_key_clean: str):
        ahora = datetime.now()
        if self.mensaje_espera_enviado.get(phone_number_key_clean) is None or \
           (ahora - self.mensaje_espera_enviado[phone_number_key_clean]).total_seconds() > 60:
            mensaje_espera = "Estoy buscando la información de tu producto, esto puede tomar un momento... ⏳ Gracias por tu paciencia."
            self.whatsapp_service.send_text_message(phone_number, mensaje_espera)
            self.mensaje_espera_enviado[phone_number_key_clean] = ahora

    async def _procesar_producto_individual_con_logica_interna(
        self, 
        producto_nombre: str, 
        raw_phone_number_with_prefix: str,
        historial_chat: list, 
        mensaje_usuario_original_completo: str, 
        cantidad_solicitada_info: int = None
    ):
        phone_number_key_clean = raw_phone_number_with_prefix.replace("whatsapp:", "")
        logger.info(f"==> Iniciando procesamiento individual para: '{producto_nombre}' (Usuario: {phone_number_key_clean}, Cantidad: {cantidad_solicitada_info})")
        
        if not producto_nombre or not producto_nombre.strip():
            logger.warning("Intento de procesar un nombre de producto vacío o nulo. Abortando búsqueda individual.")
            return {"success": False, "respuesta": "No se especificó un producto válido para buscar.", "producto_procesado": None}

        current_scraper = self.scraping_service 
        info_producto_final_para_gemini = None
        
        await self._enviar_mensaje_espera_si_necesario(raw_phone_number_with_prefix, phone_number_key_clean)

        try:
            info_producto_sheets = self.sheets_service.buscar_producto(producto_nombre, threshold=0.70)
            if info_producto_sheets:
                logger.info(f"Producto '{producto_nombre}' encontrado en Base Interna (Sheets).")
                info_producto_final_para_gemini = {
                    "opcion_mejor_precio": info_producto_sheets,
                    "opcion_entrega_inmediata": info_producto_sheets if info_producto_sheets.get("fuente") == "Base Interna" else None,
                    "tiene_doble_opcion": False
                }
            else:
                logger.info(f"Producto '{producto_nombre}' NO en Base Interna. Intentando scraping...")
                if self._can_process_scraping_throttled(phone_number_key_clean):
                    info_producto_scraped = current_scraper.buscar_producto(producto_nombre)
                    if info_producto_scraped and (info_producto_scraped.get("opcion_mejor_precio") or info_producto_scraped.get("opcion_entrega_inmediata")):
                        logger.info(f"Producto '{producto_nombre}' encontrado vía scraping.")
                        info_producto_final_para_gemini = info_producto_scraped
                        if hasattr(current_scraper, '_full_cleanup_after_phase1'):
                            logger.info(f"Ejecutando limpieza después de scraping exitoso para '{producto_nombre}'.")
                            current_scraper._full_cleanup_after_phase1()
                    else:
                        logger.info(f"Producto '{producto_nombre}' NO encontrado vía scraping.")
                else:
                    logger.info(f"Scraping throttled para '{producto_nombre}'.")
            
            if info_producto_final_para_gemini:
                es_consulta_de_cantidad = isinstance(cantidad_solicitada_info, int) and cantidad_solicitada_info > 0
                respuesta_producto_gemini = self.gemini_service.generate_product_response(
                    user_message=mensaje_usuario_original_completo, 
                    producto_info=info_producto_final_para_gemini,
                    additional_context=producto_nombre, 
                    conversation_history=historial_chat,
                    es_consulta_cantidad=es_consulta_de_cantidad,
                    cantidad_solicitada=cantidad_solicitada_info if es_consulta_de_cantidad else None
                )
                self.whatsapp_service.send_product_response(raw_phone_number_with_prefix, respuesta_producto_gemini, info_producto_final_para_gemini)
                final_user_response = respuesta_producto_gemini
            else:
                final_user_response = (f"Lo siento, no pude encontrar información para el producto '{producto_nombre}'. "
                                      "¿Podrías verificar el nombre o darme más detalles? También puedes preguntar por alternativas.")
                self.whatsapp_service.send_text_message(raw_phone_number_with_prefix, final_user_response)
            
            guardar_interaccion(phone_number_key_clean, mensaje_usuario_original_completo, final_user_response)
            self._update_circuit_breaker(success=True)
            return {"success": True, "respuesta": final_user_response, "producto_procesado": producto_nombre}

        except Exception as e:
            logger.error(f"Error severo en _procesar_producto_individual para '{producto_nombre}': {e}\n{traceback.format_exc()}")
            self._update_circuit_breaker(success=False)
            error_msg_usuario = f"Lo siento, hubo un problema técnico al obtener información para '{producto_nombre}'. Por favor, intenta de nuevo más tarde."
            self.whatsapp_service.send_text_message(raw_phone_number_with_prefix, error_msg_usuario)
            guardar_interaccion(phone_number_key_clean, mensaje_usuario_original_completo, error_msg_usuario)
            return {"success": False, "error": str(e), "producto_procesado": producto_nombre, "respuesta": error_msg_usuario}

    async def _procesar_producto_con_timeout(self, producto_nombre: str, raw_phone_number_with_prefix: str, historial: list, mensaje_original: str, cantidad_info_para_procesar: int = None):
        try:
            logger.info(f"⏳ Iniciando _procesar_producto_con_timeout para: '{producto_nombre}', Cantidad: {cantidad_info_para_procesar}")
            if not producto_nombre or not producto_nombre.strip(): 
                logger.error("Timeout: Nombre de producto vacío o nulo recibido.")
                return {"success": False, "error": "producto_vacio", "producto_procesado": None, "respuesta": "No se especificó un producto para buscar."}

            resultado = await asyncio.wait_for(
                self._procesar_producto_individual_con_logica_interna(
                    producto_nombre, 
                    raw_phone_number_with_prefix,
                    historial, 
                    mensaje_original,
                    cantidad_solicitada_info=cantidad_info_para_procesar
                ),
                timeout=self.TIMEOUT_POR_PRODUCTO
            )
            return resultado
        except asyncio.TimeoutError:
            logger.error(f"⏰ TIMEOUT procesando producto: '{producto_nombre}' después de {self.TIMEOUT_POR_PRODUCTO}s.")
            self._update_circuit_breaker(success=False)
            timeout_msg_usuario = f"Lo siento, la búsqueda para '{producto_nombre}' tomó más tiempo del esperado. Por favor, intenta de nuevo en un momento."
            self.whatsapp_service.send_text_message(raw_phone_number_with_prefix, timeout_msg_usuario)
            guardar_interaccion(raw_phone_number_with_prefix.replace("whatsapp:", ""), mensaje_original, timeout_msg_usuario)
            return {"success": False, "error": "timeout", "producto_procesado": producto_nombre, "respuesta": timeout_msg_usuario}
        except Exception as e:
            logger.error(f"❌ Error inesperado en _procesar_producto_con_timeout para '{producto_nombre}': {e}\n{traceback.format_exc()}")
            self._update_circuit_breaker(success=False)
            error_msg_usuario = f"Lo siento, ocurrió un error inesperado al procesar tu solicitud para '{producto_nombre}'. Intenta de nuevo más tarde."
            self.whatsapp_service.send_text_message(raw_phone_number_with_prefix, error_msg_usuario)
            guardar_interaccion(raw_phone_number_with_prefix.replace("whatsapp:", ""), mensaje_original, error_msg_usuario)
            return {"success": False, "error": str(e), "producto_procesado": producto_nombre, "respuesta": error_msg_usuario}


    async def procesar_mensaje(self, mensaje: str, phone_number: str, media_urls: list = None):
        start_time = time.time()
        processing_time_taken = lambda: f"{time.time() - start_time:.2f}s"
        logger.info(f"📱 [MH v3.7 OCR Dirigido] Procesando de {phone_number}: '{mensaje[:100]}{'...' if len(mensaje)>100 else ''}' | Media: {'Sí' if media_urls else 'No'}")

        if self._check_circuit_breaker():
            respuesta_cb = "🔧 Nuestro sistema está experimentando una alta carga. Por favor, inténtalo de nuevo en unos minutos."
            self.whatsapp_service.send_text_message(phone_number, respuesta_cb)
            return {"success": False, "message_type": "circuit_breaker_open", "respuesta": respuesta_cb, "processing_time": processing_time_taken()}

        clean_phone_for_db = phone_number.replace("whatsapp:", "")
        mensaje_original_usuario_texto = mensaje 
        mensaje_para_analisis_gemini = mensaje_original_usuario_texto
        
        fue_ocr = False 

        if media_urls:
            fue_ocr = True
            try:
                texto_extraido_ocr = await self.ocr_service.process_images(media_urls)

                if texto_extraido_ocr and not texto_extraido_ocr.lower().startswith("no se pudo") and texto_extraido_ocr.strip():
                    logger.info(f"📝 Texto de imagen: {texto_extraido_ocr[:100]}...")
                    mensaje_para_analisis_gemini = f"{mensaje_original_usuario_texto}\n\n[Texto de imagen]: {texto_extraido_ocr}".strip() if mensaje_original_usuario_texto else f"[Texto de imagen]: {texto_extraido_ocr}"
                    
                    mensaje_guia_ocr = (
                        "¡Hola! Soy tu asistente de INSUMOS JIP. 👍\n"
                        "He recibido tu imagen. Si es la foto de un producto en su caja, intentaré buscarlo. "
                        "Si es una imagen con una lista de varios productos, buscaré el primero que pueda identificar claramente. "
                        "Para los demás productos de la lista, por favor, envíamelos uno por uno después para que pueda ayudarte mejor. 😊"
                    )
                    self.whatsapp_service.send_text_message(phone_number, mensaje_guia_ocr)
                    guardar_interaccion(clean_phone_for_db, 
                                       mensaje_original_usuario_texto if mensaje_original_usuario_texto else "(Imagen enviada)", 
                                       mensaje_guia_ocr)
                    await asyncio.sleep(1.5) 

                elif not mensaje_original_usuario_texto: 
                    respuesta_ocr_fail = "Recibí tu imagen, pero no pude leer el texto. ¿Podrías escribir tu consulta?"
                    self.whatsapp_service.send_text_message(phone_number, respuesta_ocr_fail)
                    guardar_interaccion(clean_phone_for_db, "(Imagen sin texto legible)", respuesta_ocr_fail)
                    return {"success": True, "message_type": "ocr_failed_no_text", "respuesta": respuesta_ocr_fail, "processing_time": processing_time_taken()}
            
            except Exception as e:
                logger.error(f"❌ Error en procesamiento de OCR: {e}\n{traceback.format_exc()}")
                if not mensaje_original_usuario_texto:
                    respuesta_ocr_error = "Lo siento, hubo un problema técnico al procesar tu imagen. ¿Podrías enviar tu consulta en texto?"
                    self.whatsapp_service.send_text_message(phone_number, respuesta_ocr_error)
                    return {"success": False, "message_type": "error_ocr", "error": str(e), "respuesta": respuesta_ocr_error, "processing_time": processing_time_taken()}

        if not mensaje_para_analisis_gemini or not mensaje_para_analisis_gemini.strip(): 
            logger.info("📝 Mensaje para Gemini vacío después de OCR. Enviando saludo.")
            respuesta_vacia = self.gemini_service.generate_response("Hola", []) 
            self.whatsapp_service.send_text_message(phone_number, respuesta_vacia)
            guardar_interaccion(clean_phone_for_db, mensaje_original_usuario_texto if mensaje_original_usuario_texto else "(Mensaje vacío)", respuesta_vacia)
            return {"success": True, "message_type": "mensaje_vacio_saludo", "respuesta": respuesta_vacia, "processing_time": processing_time_taken()}

        historial = obtener_historial(clean_phone_for_db)
        contexto_gemini = self.gemini_service.analizar_contexto_con_gemini(mensaje_para_analisis_gemini, historial, is_ocr_text=fue_ocr) 
        
        tipo_consulta = contexto_gemini.get("tipo_consulta", "no_entiendo_o_irrelevante")
        productos_mencionados_directo_usuario = contexto_gemini.get("productos_mencionados_ahora", [])
        producto_principal_identificado_ocr = contexto_gemini.get("producto_principal_ocr")
        producto_contexto_anterior = contexto_gemini.get("producto_contexto_anterior")
        cantidad_solicitada_gemini = contexto_gemini.get("cantidad_solicitada")
        
        logger.info(f"🧠 Análisis Gemini: Tipo='{tipo_consulta}', ProdUsuario='{productos_mencionados_directo_usuario}', ProdOCR='{producto_principal_identificado_ocr}', ProdAntes='{producto_contexto_anterior}', Cant='{cantidad_solicitada_gemini}'")

        # --- INICIO DE HEURÍSTICA OPCIONAL ---
        service_keywords = ["entrega", "domicilio", "horario", "ubicacion", "pago", "contacto", "dirección", "teléfono"] 
        if productos_mencionados_directo_usuario:
            productos_a_mantener = []
            posible_pregunta_servicio_detectada = False
            for prod_mencionado_str in productos_mencionados_directo_usuario:
                es_frase_servicio = False
                if isinstance(prod_mencionado_str, str):
                    prod_lower = prod_mencionado_str.lower()
                    if any(keyword in prod_lower for keyword in service_keywords) and len(prod_lower.split()) > 1:
                        if not re.search(r'\b(mg|ml|g|tabs|cap|tab|comprimido|pastilla)\b', prod_lower, re.IGNORECASE):
                            es_frase_servicio = True
                            posible_pregunta_servicio_detectada = True
                            logger.warning(f"Heurística: '{prod_mencionado_str}' parece una pregunta de servicio, no un nombre de producto.")
                
                if not es_frase_servicio:
                    productos_a_mantener.append(prod_mencionado_str)
            
            if posible_pregunta_servicio_detectada:
                if not productos_a_mantener:
                    if tipo_consulta == "consulta_producto_nuevo": 
                        logger.info(f"Heurística: Reclasificando tipo_consulta de '{tipo_consulta}' a 'pregunta_general_farmacia' debido a heurística y limpiando 'productos_mencionados_directo_usuario'.")
                        tipo_consulta = "pregunta_general_farmacia" 
                    productos_mencionados_directo_usuario = [] 
                else:
                    logger.info(f"Heurística: Se eliminó una frase de servicio de 'productos_mencionados_directo_usuario'. Quedan: {productos_a_mantener}")
                    productos_mencionados_directo_usuario = productos_a_mantener
        # --- FIN DE HEURÍSTICA OPCIONAL ---

        if tipo_consulta in ["solicitud_direccion_contacto", "confirmacion_pedido", "pregunta_general_farmacia"]:
            respuesta_info = self.gemini_service.generate_response(mensaje_para_analisis_gemini, historial)
            self.whatsapp_service.send_text_message(phone_number, respuesta_info)
            guardar_interaccion(clean_phone_for_db, mensaje_para_analisis_gemini, respuesta_info)
            self._update_circuit_breaker(success=True)
            return {"success": True, "message_type": f"info_directa_{tipo_consulta}", "respuesta": respuesta_info, "processing_time": processing_time_taken()}

        if tipo_consulta == "consulta_cantidad" and isinstance(cantidad_solicitada_gemini, int) and cantidad_solicitada_gemini > 0:
            producto_objetivo_cantidad = producto_principal_identificado_ocr or \
                                         (productos_mencionados_directo_usuario[0] if productos_mencionados_directo_usuario else None) or \
                                         producto_contexto_anterior
            if producto_objetivo_cantidad:
                logger.info(f"✨ Intención: Consulta de cantidad ({cantidad_solicitada_gemini}) para '{producto_objetivo_cantidad}'.")
                resultado_cantidad = await self._procesar_producto_con_timeout(
                    producto_objetivo_cantidad, phone_number, historial, mensaje_para_analisis_gemini, cantidad_info_para_procesar=cantidad_solicitada_gemini
                )
                return {**resultado_cantidad, "message_type": f"cantidad_procesada_{'ok' if resultado_cantidad.get('success') else 'error'}", "processing_time": processing_time_taken()}
            else:
                logger.warning("Consulta de cantidad detectada por Gemini pero sin producto claro asociado.")
        
        producto_identificado_final = None
        if fue_ocr and producto_principal_identificado_ocr:
            producto_identificado_final = producto_principal_identificado_ocr
            logger.info(f"OCR: Se procesará el producto principal del OCR: '{producto_identificado_final}'")
        elif productos_mencionados_directo_usuario: 
            if len(productos_mencionados_directo_usuario) > 1:
                 logger.info(f"🎯 Múltiples productos en TEXTO ({len(productos_mencionados_directo_usuario)}): {productos_mencionados_directo_usuario}. Solicitando uno por uno.")
                 mensaje_instr = self._generar_mensaje_instrucciones_multiples(productos_mencionados_directo_usuario, mensaje_original_usuario_texto)
                 self.whatsapp_service.send_text_message(phone_number, mensaje_instr)
                 guardar_interaccion(clean_phone_for_db, mensaje_para_analisis_gemini, mensaje_instr)
                 self._update_circuit_breaker(success=True)
                 return {"success": True, "message_type": "instrucciones_multiples_productos_texto", "respuesta": mensaje_instr, "processing_time": processing_time_taken()}
            else: 
                producto_identificado_final = productos_mencionados_directo_usuario[0]
        elif tipo_consulta == "pregunta_sobre_producto_en_contexto" and producto_contexto_anterior: 
            producto_identificado_final = producto_contexto_anterior
        
        if not producto_identificado_final and not fue_ocr and tipo_consulta in ["otro", "no_entiendo_o_irrelevante", "respuesta_a_pregunta_bot", "pregunta_general_farmacia"]:
            productos_locales = self._detectar_productos_locales_simples(mensaje_para_analisis_gemini)
            if productos_locales:
                producto_identificado_final = productos_locales[0] 
                logger.info(f"Fallback local: Se procesará '{producto_identificado_final}'")


        if producto_identificado_final:
            logger.info(f"🔍 Procesando producto único validado: '{producto_identificado_final}'")
            resultado_unico = await self._procesar_producto_con_timeout(
                producto_identificado_final, phone_number, historial, mensaje_para_analisis_gemini, cantidad_info_para_procesar=None
            )
            return {**resultado_unico, "message_type": f"producto_unico_{'ok' if resultado_unico.get('success') else 'error'}", "processing_time": processing_time_taken()}
        
        if fue_ocr and not producto_principal_identificado_ocr:
            logger.info("💬 OCR procesado, pero Gemini no identificó un producto principal claro de la imagen. Usuario ya fue guiado.")
            guardar_interaccion(clean_phone_for_db, mensaje_para_analisis_gemini, "(Imagen procesada, no se identificó producto para búsqueda automática)")
            return {"success": True, "message_type": "ocr_sin_producto_principal_identificado", "respuesta": "(Imagen procesada, no se identificó producto para búsqueda automática)", "processing_time": processing_time_taken()}

        logger.info(f"💬 No se identificó un producto específico para buscar. Tipo consulta: '{tipo_consulta}'. Generando respuesta general.")
        respuesta_final_gemini = self.gemini_service.generate_response(mensaje_para_analisis_gemini, historial)
        self.whatsapp_service.send_text_message(phone_number, respuesta_final_gemini)
        guardar_interaccion(clean_phone_for_db, mensaje_para_analisis_gemini, respuesta_final_gemini)
        self._update_circuit_breaker(success=True)
        return {"success": True, "message_type": f"respuesta_gemini_{tipo_consulta}", "respuesta": respuesta_final_gemini, "processing_time": processing_time_taken()}
