"""
Servicio para interactuar con Google Sheets como base de datos interna.
Proporciona funcionalidades para buscar productos en la hoja de cálculo
antes de recurrir a los scrapers.

VERSIÓN MEJORADA:
- Threshold reducido de 0.7 a 0.5 para mayor flexibilidad
- Algoritmo de similitud mejorado con normalización de acentos
- Mejor manejo de coincidencias exactas de palabras
- Puntuación mejorada para productos específicos
- Comparación de dosis para refinar la similitud
"""
import os
import re
import time
import logging
import unicodedata
from typing import Dict, List, Optional, Tuple, Any, Union

# Importaciones para Google Sheets
import google.auth
import gspread
from google.oauth2 import service_account

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class SheetsService:
    """
    Servicio para interactuar con la base de datos interna en Google Sheets.
    Proporciona métodos para buscar productos por nombre o código.
    
    VERSIÓN MEJORADA con algoritmo de similitud más flexible y comparación de dosis.
    """
    
    def __init__(self):
        """
        Inicializa el servicio de Google Sheets utilizando las credenciales
        predeterminadas del entorno o un archivo específico.
        """
        self.data = []
        self.last_refresh = 0
        self.cache_ttl = 300  # Segundos de validez del caché (5 minutos)
        self.sheet_id = None
        self.client = None
        self.spreadsheet = None
        self.sheet = None
        
        try:
            self.sheet_id = os.getenv('SHEETS_ID')
            if not self.sheet_id:
                logger.warning("SHEETS_ID no está configurado en las variables de entorno")
                return
            
            scopes = [
                'https://www.googleapis.com/auth/spreadsheets',
                'https://www.googleapis.com/auth/drive'
            ]
            
            try:
                credentials, project = google.auth.default(scopes=scopes)
                logger.info(f"Usando credenciales predeterminadas del proyecto: {project}")
            except Exception as e:
                logger.error(f"Error al cargar credenciales predeterminadas: {e}")
                import traceback
                logger.error(traceback.format_exc())
                return
            
            self.client = gspread.authorize(credentials)
            self.spreadsheet = self.client.open_by_key(self.sheet_id)
            self.sheet = self.spreadsheet.sheet1
            
            self.refresh_cache_if_needed(force=True)
            
            logger.info(f"SheetsService inicializado correctamente. Cargados {len(self.data)} productos.")
        except Exception as e:
            logger.error(f"Error al inicializar SheetsService: {e}")
            import traceback
            logger.error(traceback.format_exc())
    
    def refresh_cache_if_needed(self, force=False) -> bool:
        current_time = time.time()
        if not force and (current_time - self.last_refresh) < self.cache_ttl:
            return False
        
        if not self.sheet:
            logger.error("No hay conexión a la hoja de cálculo, no se puede actualizar caché")
            return False
        
        try:
            self.data = self.sheet.get_all_records()
            self.last_refresh = current_time
            logger.info(f"Caché actualizado: {len(self.data)} registros cargados")
            return True
        except Exception as e:
            logger.error(f"Error al actualizar caché: {e}")
            return False
    
    def normalize_text(self, text: str) -> str:
        if not text:
            return ""
        
        normalized = text.lower()
        normalized = unicodedata.normalize('NFD', normalized)
        normalized = ''.join(c for c in normalized if unicodedata.category(c) != 'Mn')
        normalized = re.sub(r'[^\w\s]', ' ', normalized)
        normalized = re.sub(r'\s+', ' ', normalized).strip()
        
        return normalized
    
    def normalize_product_name(self, product_name: str) -> str:
        if not product_name:
            return ""
        
        normalized = self.normalize_text(product_name)
        
        words_to_remove = ["el ", "la ", "los ", "las ", "un ", "una ", "unos ", "unas ", "de ", "del "]
        for word in words_to_remove:
            if normalized.startswith(word):
                normalized = normalized[len(word):]
        
        replacements = {
            "acido": "ácido", # Aunque normalize_text quita acentos, aquí es por si se escribe sin acento intencionalmente
            "acetato": "ac",
            "capsulas": "cap",
            "tabletas": "tab",
            "solucion": "sol",
            "inyectable": "iny",
            "miligramos": "mg",
            "mililitros": "ml",
            "microgramos": "mcg"
            # Podríamos añadir más normalizaciones de unidades si es necesario, ej. "gramos" -> "g"
        }
        
        # Aplicar reemplazos de unidades/formas de manera segura palabra por palabra
        # para evitar reemplazar subcadenas incorrectamente (ej. "sol" en "girasol")
        words = normalized.split()
        processed_words = []
        for word in words:
            # Normalizar palabra si es una forma farmacéutica o unidad completa
            # Esto es más seguro que un replace directo en toda la cadena
            if word in replacements:
                 processed_words.append(replacements[word])
            # Específicamente para unidades que pueden estar pegadas a números como "100mg"
            # o separadas "100 mg", y queremos que el _extract_dosage las encuentre.
            # La normalización de "miligramos" a "mg" ya ayuda.
            # No es necesario más manipulación aquí si _extract_dosage es robusto.
            else:
                 processed_words.append(word)
        
        normalized = " ".join(processed_words)
        
        return normalized.strip()

    def _extract_dosage(self, text_norm: str) -> tuple[str | None, str | None]:
        """
        Extrae el valor numérico y la unidad de una dosis de un texto normalizado.
        Ej: "producto 100 mg" -> ("100", "mg")
             "producto 50ml" -> ("50", "ml")
        Args:
            text_norm (str): Texto normalizado (minúsculas, sin acentos).
        Returns:
            tuple: (valor_str, unidad_str) o (None, None) si no se encuentra dosis.
        """
        # Unidades comunes abreviadas que ya deberían estar normalizadas por normalize_product_name
        # y normalize_text (ej. miligramos -> mg)
        # La regex busca: número (posiblemente decimal), espacio opcional, unidad seguida de un límite de palabra.
        # Se añaden más unidades para ser más robusto, asumiendo que normalize_product_name
        # o normalize_text las han llevado a estas formas abreviadas y en minúsculas.
        match = re.search(r"(\d+[\.,]?\d*)\s*(mg|ml|mcg|g|ui|l|kg|unidades|unidad|unid)\b", text_norm)
        if match:
            value_str = match.group(1).replace(',', '.')  # Normalizar coma a punto para float
            unit_str = match.group(2).lower() # Unidad ya debería estar en minúscula por normalize_text
            return value_str, unit_str
        return None, None

    def calculate_similarity(self, query: str, target: str) -> float:
        """
        MEJORADO: Calcula la similitud entre dos cadenas de texto.
        Ahora con mejor normalización, lógica de puntuación más inteligente y
        COMPARACIÓN DE DOSIS ESPECÍFICA.
        
        Args:
            query (str): Consulta (se normalizará internamente si no lo está)
            target (str): Texto objetivo (se normalizará internamente si no lo está)
            
        Returns:
            float: Puntuación de similitud entre 0 y 1
        """
        if not query or not target:
            return 0.0
        
        # query_norm y target_norm deben ser el resultado de self.normalize_product_name()
        # o al menos self.normalize_text() para que la extracción de dosis y comparación de palabras funcione.
        # Si 'query' y 'target' ya son nombres de producto normalizados, podemos omitir
        # la normalización aquí, pero es más seguro hacerlo.
        query_norm = self.normalize_text(query) 
        target_norm = self.normalize_text(target)
        
        query_words = set(query_norm.split())
        target_words = set(target_norm.split())
        
        if not query_words or not target_words:
            return 0.0
        
        common_words = query_words.intersection(target_words)
        
        # Puntuación base: porcentaje de palabras de la consulta que están en el objetivo.
        base_score = len(common_words) / len(query_words) if query_words else 0.0
        
        # BONIFICACIONES
        query_start = query_norm[:min(10, len(query_norm))]
        if target_norm.startswith(query_start) and len(query_start) > 3:
            base_score += 0.25
            logger.debug(f"🎯 Bonus inicio: '{query_start}' encontrado al inicio de '{target_norm[:20]}...'")
        
        if len(common_words) >= 2:
            density_bonus = min(0.15, len(common_words) * 0.05)
            base_score += density_bonus
            logger.debug(f"📊 Bonus densidad: {len(common_words)} palabras comunes = +{density_bonus:.2f}")
        
        main_query_words = [w for w in query_words if len(w) > 3]
        if main_query_words:
            main_word = max(main_query_words, key=len, default=None) # default=None para evitar error si está vacío
            if main_word and main_word in target_words:
                base_score += 0.1
                logger.debug(f"🔑 Bonus palabra principal: '{main_word}' encontrada")
        
        # PENALIZACIÓN por longitud
        length_ratio = len(query_words) / len(target_words) if target_words else 0.0
        if length_ratio < 0.3:  # Target es más de 3 veces más largo
            base_score *= 0.95
            logger.debug(f"📏 Penalización longitud: ratio {length_ratio:.2f}")

        # --- INICIO: LÓGICA DE COMPARACIÓN DE DOSIS ---
        query_dosage_val_str, query_dosage_unit = self._extract_dosage(query_norm)
        target_dosage_val_str, target_dosage_unit = self._extract_dosage(target_norm)

        dosage_factor = 1.0
        log_msg_dosage_details = ""

        if query_dosage_val_str and query_dosage_unit:
            log_msg_dosage_details = f"QueryDose='{query_dosage_val_str}{query_dosage_unit}' "
            if target_dosage_val_str and target_dosage_unit:
                log_msg_dosage_details += f"TargetDose='{target_dosage_val_str}{target_dosage_unit}'. "
                try:
                    q_val = float(query_dosage_val_str)
                    t_val = float(target_dosage_val_str)
                    
                    if q_val == t_val and query_dosage_unit == target_dosage_unit:
                        dosage_factor = 1.35  # Bonificación significativa
                        log_msg_dosage_details += "EXACT_MATCH"
                    else:
                        dosage_factor = 0.5  # Penalización fuerte
                        log_msg_dosage_details += "MISMATCH"
                except ValueError:
                    logger.warning(f"Error al convertir dosis a float: q='{query_dosage_val_str}', t='{target_dosage_val_str}'")
                    if query_dosage_unit == target_dosage_unit: # Mismas unidades pero valor no numérico claro
                        dosage_factor = 0.7 
                        log_msg_dosage_details += "CONV_ERR_SAME_UNIT"
                    else: # Unidades diferentes y valor no numérico
                        log_msg_dosage_details += "CONV_ERR_DIFF_UNIT"
            else: # Query tiene dosis, target no
                dosage_factor = 0.75
                log_msg_dosage_details += "TARGET_NO_DOSE"
            logger.debug(f"💊 {log_msg_dosage_details} FactorDosis={dosage_factor:.2f}")
        
        base_score *= dosage_factor
        # --- FIN: LÓGICA DE COMPARACIÓN DE DOSIS ---

        final_score = min(max(base_score, 0.0), 1.0) # Clampear entre 0 y 1
        
        if final_score > 0.3:
            logger.debug(f"💯 Similitud FINAL: {final_score:.3f} | Query: '{query_norm}' | Target: '{target_norm[:50]}...' | {log_msg_dosage_details if (query_dosage_val_str and query_dosage_unit) else 'Sin dosis en query'}")
        
        return final_score

    def search_product(self, product_name: str, threshold: float = 0.5) -> Optional[Dict[str, Any]]:
        self.refresh_cache_if_needed()
        
        if not product_name or not self.data:
            logger.warning(f"[DEBUG] No hay búsqueda posible: producto='{product_name}', datos={len(self.data)}")
            return None
        
        normalized_query = self.normalize_product_name(product_name)
        if not normalized_query:
            logger.warning(f"[DEBUG] Búsqueda normalizada vacía para: '{product_name}'")
            return None
        
        logger.info(f"[DEBUG] Búsqueda MEJORADA (con dosis): '{normalized_query}' (original: '{product_name}') | Threshold: {threshold}")
        
        best_match = None
        best_score = 0.0 # Asegurar que es float
        candidates = []
        
        for product_row in self.data: # Renombrar 'product' a 'product_row' para evitar confusión
            desc = product_row.get('DESCRIPCION', '')
            if not desc:
                continue
                
            normalized_desc = self.normalize_product_name(desc) # Normalizar descripción del producto de la hoja
            
            # No llamar a self.calculate_similarity(normalized_query, desc)
            # sino self.calculate_similarity(normalized_query, normalized_desc)
            # O mejor, pasar los nombres ya normalizados completamente si calculate_similarity lo espera
            # Aquí, pasaremos los nombres que ya han pasado por normalize_product_name
            # y calculate_similarity internamente usará normalize_text para la forma más básica.
            # Para que _extract_dosage funcione bien, necesita el texto después de normalize_product_name.
            score = self.calculate_similarity(normalized_query, normalized_desc) # Usar descripciones normalizadas
            
            product_code = str(product_row.get('CLAVE', '')).lower()
            # query_just_text_normalized es normalized_query pero sin la dosis, si queremos comparar código
            # Esto es complicado. Por ahora, si el código coincide con la query normalizada completa, damos bonus.
            if product_code and normalized_query == product_code: # Comparar con la query normalizada
                score = min(score + 0.5, 1.0) # Aumentar puntuación, pero no pasar de 1.0
                logger.info(f"[DEBUG] 🔑 Bonus por código coincidente: {product_code}, score ahora {score:.3f}")
                
            if score > 0.3:
                candidates.append({
                    'score': score,
                    'name': desc, # Guardar nombre original para mostrar
                    'normalized': normalized_desc # Guardar nombre normalizado para debug
                })
                
            if score > threshold:
                logger.info(f"[DEBUG] ✅ Candidato VÁLIDO ({score:.3f}): '{desc}'")
                
            if score > best_score and score >= threshold:
                best_score = score
                best_match = product_row
        
        if candidates:
            logger.info(f"[DEBUG] 📊 Top candidatos encontrados (ordenados por score):")
            sorted_candidates = sorted(candidates, key=lambda x: x['score'], reverse=True)
            for i, candidate in enumerate(sorted_candidates[:5]):
                status = "✅ ACEPTADO" if candidate['score'] >= threshold else "❌ RECHAZADO"
                logger.info(f"   #{i+1}: {candidate['score']:.3f} - {candidate['name'][:50]}... (Norm: '{candidate['normalized'][:50]}...') [{status}]")
        
        if best_match:
            logger.info(f"[DEBUG] 🏆 MEJOR COINCIDENCIA ({best_score:.3f}): '{best_match.get('DESCRIPCION', '')}'")
        else:
            logger.info(f"[DEBUG] ❌ Sin coincidencias que superen threshold ({threshold}) para '{normalized_query}'")
            if candidates: # Mostrar el mejor aunque no haya superado el threshold
                best_rejected_candidate = max(candidates, key=lambda x: x['score'])
                if best_rejected_candidate['score'] < threshold :
                    logger.info(f"[DEBUG] 💡 Mejor candidato RECHAZADO ({best_rejected_candidate['score']:.3f}): '{best_rejected_candidate['name'][:50]}...'")
                    if best_rejected_candidate['score'] > 0.0: # Solo sugerir si hay alguna similitud
                         sugg_threshold = float(f"{best_rejected_candidate['score'] - 0.05:.2f}")
                         logger.info(f"[DEBUG] 💡 Sugerencia: Considera reducir threshold a ~{max(0.1, sugg_threshold)}")

        return best_match
    
    def format_product(self, product_data: Dict[str, Any]) -> Dict[str, Any]:
        stock = product_data.get('EXISTENCIAS', product_data.get('EXISTENCIA', 0))
        stock_value = 0
        try:
            stock_value = int(float(stock))
        except (ValueError, TypeError):
            if isinstance(stock, str) and any(word in stock.lower() for word in ['si', 'disponible']):
                stock_value = 1
        
        price = product_data.get('PRECIO', 0)
        price_str = ""
        price_value = 0.0

        if price: #Solo procesar si price no es None o 0
            try:
                # Intenta convertir directamente a float primero
                price_value = float(price)
                price_str = f"${price_value:.2f}"
            except ValueError: # Si falla, es probable que sea un string con formato
                if isinstance(price, str):
                    clean_price_for_float = price.replace('$', '').replace(',', '').strip()
                    try:
                        price_value = float(clean_price_for_float)
                        price_str = f"${price_value:.2f}" # Re-formatear estandarizado
                    except ValueError:
                        price_str = str(price) # Usar el string original si no se puede convertir
                        price_value = 0.0 # O intentar extraer de nuevo con regex más permisivo
                        # match_pv = re.search(r'(\d+(\.\d+)?)', clean_price_for_float)
                        # if match_pv: price_value = float(match_pv.group(1))

        else: # Si el precio es 0, None, o string vacío
            price_str = "$0.00"
            price_value = 0.0

        return {
            "nombre": product_data.get('DESCRIPCION', ''),
            "codigo_barras": str(product_data.get('CLAVE', '')),
            "laboratorio": product_data.get('LABORATORIO', 'No especificado'),
            "registro_sanitario": product_data.get('REGISTRO', ''),
            "precio": price_str, # Precio formateado como string
            "existencia": str(stock_value), # Existencia como string
            "existencia_numerica": stock_value, # Existencia como número
            "precio_numerico": price_value, # Precio como float para cálculos
            "fuente": "Base Interna",
            "nombre_farmacia": "SOPRIM", # O el nombre que corresponda
            "estado": "encontrado" # Asumimos que si se formatea, se encontró
        }
    
    def buscar_producto(self, nombre_producto: str, threshold: float = 0.5) -> Optional[Dict[str, Any]]:
        try:
            if not self.sheet_id:
                logger.warning("[DEBUG] No hay hoja de cálculo configurada. Omitiendo búsqueda interna.")
                return None
            
            logger.info(f"[DEBUG] 🚀 Iniciando búsqueda MEJORADA (con dosis) para: '{nombre_producto}' con threshold {threshold}")
            
            producto_encontrado_row = self.search_product(nombre_producto, threshold) # search_product devuelve la fila
            
            if producto_encontrado_row:
                resultado = self.format_product(producto_encontrado_row) # Formatear la fila
                logger.info(f"[DEBUG] ✅ Producto encontrado en base interna: {resultado['nombre']} (similitud >= {threshold})")
                return resultado
            
            logger.info(f"[DEBUG] ❌ No se encontró '{nombre_producto}' en la base interna (threshold: {threshold})")
            return None
        except Exception as e:
            logger.error(f"[DEBUG] ❌ Error buscando producto '{nombre_producto}': {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None
    
    def buscar_por_codigo(self, codigo: str) -> Optional[Dict[str, Any]]:
        try:
            self.refresh_cache_if_needed()
            codigo_norm = str(codigo).strip().upper()
            
            for producto_row in self.data:
                producto_codigo = str(producto_row.get('CLAVE', '')).strip().upper()
                if producto_codigo == codigo_norm:
                    resultado = self.format_product(producto_row)
                    logger.info(f"Producto encontrado por código '{codigo}': {resultado['nombre']}")
                    return resultado
            
            logger.info(f"No se encontró producto con código '{codigo}' en la base interna")
            return None
        except Exception as e:
            logger.error(f"Error buscando producto por código '{codigo}': {e}")
            return None
    
    def get_all_products(self) -> List[Dict[str, Any]]:
        try:
            self.refresh_cache_if_needed()
            return [self.format_product(p) for p in self.data]
        except Exception as e:
            logger.error(f"Error obteniendo todos los productos: {e}")
            return []
    
    def get_products_with_stock(self) -> List[Dict[str, Any]]:
        try:
            self.refresh_cache_if_needed()
            productos_con_stock = []
            for p_row in self.data:
                # Usar format_product para obtener existencia_numerica estandarizada
                producto_formateado = self.format_product(p_row)
                if producto_formateado['existencia_numerica'] > 0:
                    productos_con_stock.append(producto_formateado)
            return productos_con_stock
        except Exception as e:
            logger.error(f"Error obteniendo productos con stock: {e}")
            return []
