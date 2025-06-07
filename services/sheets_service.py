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
            "acido": "ácido", 
            "acetato": "ac",
            "capsulas": "cap",
            "tabletas": "tab",
            "solucion": "sol",
            "inyectable": "iny",
            "miligramos": "mg",
            "mililitros": "ml",
            "microgramos": "mcg"
        }
        
        words = normalized.split()
        processed_words = []
        for word in words:
            if word in replacements:
                 processed_words.append(replacements[word])
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
        match = re.search(r"(\d+[\.,]?\d*)\s*(mg|ml|mcg|g|ui|l|kg|unidades|unidad|unid)\b", text_norm)
        if match:
            value_str = match.group(1).replace(',', '.')
            unit_str = match.group(2).lower() 
            return value_str, unit_str
        return None, None

    def calculate_similarity(self, query: str, target: str) -> float:
        """
        CORREGIDO: Calcula la similitud priorizando el nombre del producto y usando la dosis como factor.
        
        Args:
            query (str): Consulta (ya normalizada por normalize_product_name)
            target (str): Texto objetivo (ya normalizado por normalize_product_name)
            
        Returns:
            float: Puntuación de similitud entre 0 y 1
        """
        query_norm_for_text_processing = self.normalize_text(query)
        target_norm_for_text_processing = self.normalize_text(target)

        if not query_norm_for_text_processing or not target_norm_for_text_processing:
            return 0.0

        # 1. Extraer dosis de la consulta y del objetivo
        query_dosage_val_str, query_dosage_unit = self._extract_dosage(query_norm_for_text_processing)
        target_dosage_val_str, target_dosage_unit = self._extract_dosage(target_norm_for_text_processing)

        # 2. Calcular factor de dosis
        dosage_factor = 1.0
        log_msg_dosage_details = ""
        query_has_dose = bool(query_dosage_val_str and query_dosage_unit)
        target_has_dose = bool(target_dosage_val_str and target_dosage_unit)

        if query_has_dose and target_has_dose:
            log_msg_dosage_details = f"QueryDose='{query_dosage_val_str}{query_dosage_unit}' TargetDose='{target_dosage_val_str}{target_dosage_unit}'. "
            try:
                q_val = float(query_dosage_val_str)
                t_val = float(target_dosage_val_str)
                if q_val == t_val and query_dosage_unit == target_dosage_unit:
                    dosage_factor = 1.1  # Bonificación leve por coincidencia exacta de dosis
                    log_msg_dosage_details += "EXACT_DOSE_MATCH"
                elif query_dosage_unit == target_dosage_unit: # Misma unidad, diferente valor
                    dosage_factor = 0.4  # Penalización por valor diferente
                    log_msg_dosage_details += "VALUE_MISMATCH"
                else: # Unidades diferentes
                    dosage_factor = 0.2  # Penalización fuerte por unidades diferentes
                    log_msg_dosage_details += "UNIT_MISMATCH"
            except ValueError:
                logger.warning(f"Error al convertir dosis a float: q='{query_dosage_val_str}', t='{target_dosage_val_str}'")
                dosage_factor = 0.1  # Penalización fuerte por error de conversión
                log_msg_dosage_details += "CONV_ERROR"
        elif query_has_dose and not target_has_dose: # Consulta con dosis, objetivo sin dosis
            dosage_factor = 0.1  # Penalización muy fuerte
            log_msg_dosage_details = f"QueryDose='{query_dosage_val_str}{query_dosage_unit}' TargetHasNoDose. STRONG_PENALTY"
        elif not query_has_dose and target_has_dose: # Consulta sin dosis, objetivo con dosis
            dosage_factor = 1.0 
            log_msg_dosage_details = f"QueryHasNoDose TargetDose='{target_dosage_val_str}{target_dosage_unit}'. MINIMAL_OR_NO_PENALTY_FOR_TARGET_SPECIFICITY"
        else: # Ni consulta ni objetivo tienen dosis
            log_msg_dosage_details = "NoDoseInQueryOrTarget. NEUTRAL"
            dosage_factor = 1.0 

        # 3. Obtener palabras del nombre (excluyendo la dosis)
        query_name_str = query_norm_for_text_processing
        if query_has_dose:
            q_dose_pattern = rf"\b{re.escape(query_dosage_val_str)}\s*{re.escape(query_dosage_unit)}\b|\b{re.escape(query_dosage_val_str)}{re.escape(query_dosage_unit)}\b"
            query_name_str = re.sub(q_dose_pattern, "", query_name_str, count=1, flags=re.IGNORECASE).strip()
        query_name_words = set(w for w in query_name_str.split() if w)

        target_name_str = target_norm_for_text_processing
        if target_has_dose:
            t_dose_pattern = rf"\b{re.escape(target_dosage_val_str)}\s*{re.escape(target_dosage_unit)}\b|\b{re.escape(target_dosage_val_str)}{re.escape(target_dosage_unit)}\b"
            target_name_str = re.sub(t_dose_pattern, "", target_name_str, count=1, flags=re.IGNORECASE).strip()
        target_name_words = set(w for w in target_name_str.split() if w)
        
        if not query_name_words:
            if query_has_dose and target_has_dose and dosage_factor > 0.5: 
                 base_score_for_dose_only_match = 0.4 
                 final_score = min(base_score_for_dose_only_match * dosage_factor, 1.0)
                 logger.debug(f"💯 Similitud (solo dosis en query): {final_score:.3f} | Query: '{query_norm_for_text_processing}' | Target: '{target_norm_for_text_processing[:50]}...'")
                 return final_score
            return 0.0 

        # 4. Calcular similitud basada en las palabras del nombre
        common_name_words = query_name_words.intersection(target_name_words)
        
        # --- MODIFICACIÓN AQUÍ: Cambiar de Jaccard a len(common)/len(query) para name_score ---
        if not query_name_words: 
            name_score = 0.0
        else:
            name_score = len(common_name_words) / len(query_name_words)
        # --- FIN DE LA MODIFICACIÓN ---
            
        current_score_for_name_logic = name_score

        # 5. Aplicar bonificaciones y penalizaciones al `current_score_for_name_logic`
        query_start_name = query_name_str[:min(10, len(query_name_str))]
        if target_name_str.startswith(query_start_name) and len(query_start_name) > 2:
            current_score_for_name_logic += 0.20 
            logger.debug(f"🎯 Bonus inicio (nombre): '{query_start_name}' encontrado al inicio de '{target_name_str[:20]}...'")
        
        if query_name_words and (len(common_name_words) / len(query_name_words)) > 0.49 :
            if len(common_name_words) >=1 : # Asegurar al menos una palabra común del nombre
                 current_score_for_name_logic += 0.15 
                 logger.debug(f"📊 Bonus palabras nombre comunes: {len(common_name_words)} de {len(query_name_words)} coinciden ({len(common_name_words) / len(query_name_words):.2f})")
        
        main_query_name_word_list = [w for w in query_name_words if len(w) > 3]
        if main_query_name_word_list:
            main_name_word = max(main_query_name_word_list, key=len, default=None)
            if main_name_word and main_name_word in target_name_words:
                current_score_for_name_logic += 0.10
                logger.debug(f"🔑 Bonus palabra principal (nombre): '{main_name_word}' encontrada")
        
        if target_name_words and query_name_words: # Evitar división por cero si alguno está vacío (aunque query_name_words ya se verificó)
            length_ratio_name = len(query_name_words) / len(target_name_words) if len(target_name_words) > 0 else 100 # Evitar div por cero
            if length_ratio_name < 0.4: 
                current_score_for_name_logic *= 0.90
                logger.debug(f"📏 Penalización longitud (nombre): ratio {length_ratio_name:.2f}")
            elif length_ratio_name > 2.5: 
                current_score_for_name_logic *= 0.90
                logger.debug(f"📏 Penalización longitud (nombre inverso): ratio {length_ratio_name:.2f}")
        
        # 6. Combinar la puntuación del nombre con el factor de dosis
        final_score = current_score_for_name_logic * dosage_factor
        
        # 7. Asegurar que la puntuación final esté entre 0 y 1
        final_score = min(max(final_score, 0.0), 1.0)
        
        if final_score > 0.2: 
            logger.debug(f"💯 Similitud CORREGIDA: {final_score:.3f} | Q: '{query_norm_for_text_processing}' | T: '{target_norm_for_text_processing[:50]}...'")
            logger.debug(f"  ScoreNombreBase(len(common)/len(query))={name_score:.3f} -> ScoreNombreAjustado={current_score_for_name_logic:.3f}")
            logger.debug(f"  {log_msg_dosage_details} FactorDosis={dosage_factor:.2f}")
            logger.debug(f"  Q_NameWords='{query_name_words}', T_NameWords='{target_name_words}'")
        
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
        best_score = 0.0 
        candidates = []
        
        for product_row in self.data: 
            desc = product_row.get('DESCRIPCION', '')
            if not desc:
                continue
                
            normalized_desc = self.normalize_product_name(desc) 
            
            score = self.calculate_similarity(normalized_query, normalized_desc)
            
            product_code = str(product_row.get('CLAVE', '')).lower()
            if product_code and normalized_query == product_code: 
                score = min(score + 0.5, 1.0) 
                logger.info(f"[DEBUG] 🔑 Bonus por código coincidente: {product_code}, score ahora {score:.3f}")
                
            if score > 0.3: 
                candidates.append({
                    'score': score,
                    'name': desc, 
                    'normalized': normalized_desc 
                })
                
            if score >= threshold : 
                logger.info(f"[DEBUG] ✅ Candidato VÁLIDO ({score:.3f}) para '{normalized_query}': '{desc}' (Norm: '{normalized_desc}')")
                if score > best_score: 
                    best_score = score
                    best_match = product_row
            elif score > 0.3 : 
                 logger.info(f"[DEBUG] 🟡 Candidato CERCANO pero NO VÁLIDO ({score:.3f}) para '{normalized_query}': '{desc}' (Norm: '{normalized_desc}')")

        if candidates:
            logger.info(f"[DEBUG] 📊 Top candidatos encontrados (ordenados por score) para '{normalized_query}':")
            sorted_candidates = sorted(candidates, key=lambda x: x['score'], reverse=True)
            for i, candidate in enumerate(sorted_candidates[:5]):
                status = "✅ ACEPTADO" if candidate['score'] >= threshold else "❌ RECHAZADO"
                logger.info(f"   #{i+1}: {candidate['score']:.3f} - {candidate['name'][:50]}... (Norm: '{candidate['normalized'][:50]}...') [{status}]")
        
        if best_match:
            logger.info(f"[DEBUG] 🏆 MEJOR COINCIDENCIA para '{normalized_query}' ({best_score:.3f}): '{best_match.get('DESCRIPCION', '')}'")
        else:
            logger.info(f"[DEBUG] ❌ Sin coincidencias que superen threshold ({threshold}) para '{normalized_query}'")
            if candidates: 
                best_rejected_candidate = max(candidates, key=lambda x: x['score'])
                if best_rejected_candidate['score'] < threshold :
                    logger.info(f"[DEBUG] 💡 Mejor candidato RECHAZADO ({best_rejected_candidate['score']:.3f}): '{best_rejected_candidate['name'][:50]}...'")
                    if best_rejected_candidate['score'] > 0.0: 
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

        if price: 
            try:
                price_value = float(price)
                price_str = f"${price_value:.2f}"
            except ValueError: 
                if isinstance(price, str):
                    clean_price_for_float = price.replace('$', '').replace(',', '').strip()
                    try:
                        price_value = float(clean_price_for_float)
                        price_str = f"${price_value:.2f}" 
                    except ValueError:
                        price_str = str(price) 
                        price_value = 0.0 
        else: 
            price_str = "$0.00"
            price_value = 0.0

        return {
            "nombre": product_data.get('DESCRIPCION', ''),
            "codigo_barras": str(product_data.get('CLAVE', '')),
            "laboratorio": product_data.get('LABORATORIO', 'No especificado'),
            "registro_sanitario": product_data.get('REGISTRO', ''),
            "precio": price_str, 
            "existencia": str(stock_value), 
            "existencia_numerica": stock_value, 
            "precio_numerico": price_value, 
            "fuente": "Base Interna",
            "nombre_farmacia": "SOPRIM", 
            "estado": "encontrado" 
        }
    
    def buscar_producto(self, nombre_producto: str, threshold: float = 0.5) -> Optional[Dict[str, Any]]:
        try:
            if not self.sheet_id:
                logger.warning("[DEBUG] No hay hoja de cálculo configurada. Omitiendo búsqueda interna.")
                return None
            
            logger.info(f"[DEBUG] 🚀 Iniciando búsqueda MEJORADA (con dosis) para: '{nombre_producto}' con threshold {threshold}")
            
            producto_encontrado_row = self.search_product(nombre_producto, threshold) 
            
            if producto_encontrado_row:
                resultado = self.format_product(producto_encontrado_row) 
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
                producto_formateado = self.format_product(p_row)
                if producto_formateado['existencia_numerica'] > 0:
                    productos_con_stock.append(producto_formateado)
            return productos_con_stock
        except Exception as e:
            logger.error(f"Error obteniendo productos con stock: {e}")
            return []
