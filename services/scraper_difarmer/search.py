#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import time
import re
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

# Asegúrate de que este import funcione en tu estructura de proyecto
# Si 'settings' está en el mismo directorio, podría ser:
# from settings import TIMEOUT, logger
# Si es un paquete, '.settings' es correcto.
# Por ahora, lo comentaré para que el código sea ejecutable en un solo archivo si es necesario.
# from .settings import TIMEOUT, logger

# Placeholder para logger si no se importa
import logging
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO) # Configuración básica de logging


def extraer_concentracion(texto):
    """
    Extrae concentración del texto (200mg/5ml, 500mg, etc.)
    
    Args:
        texto (str): Texto del cual extraer concentración
        
    Returns:
        str: Concentración normalizada o None
    """
    if not texto:
        return None
    
    texto_lower = texto.lower()
    
    # Patrones para detectar concentraciones
    # El segundo patrón para mg/ml es redundante si el primero ya usa \s*
    patrones = [
        r'(\d+(?:\.\d+)?)\s*mg\s*/\s*(\d+(?:\.\d+)?)\s*ml',  # 200mg/5ml o 200 MG / 5 ML
        r'(\d+(?:\.\d+)?)\s*mg',  # 500mg
        r'(\d+(?:\.\d+)?)\s*g',   # 1g
        r'(\d+(?:\.\d+)?)\s*mcg', # 100mcg
    ]
    
    for patron in patrones:
        match = re.search(patron, texto_lower)
        if match:
            if '/ml' in patron: # Específicamente mg/ml
                mg = match.group(1)
                ml = match.group(2)
                return f"{mg}mg/{ml}ml"
            else:
                # Formato simple
                valor = match.group(1)
                if 'mg' in patron: # Asegurar que la unidad correcta se añade
                    return f"{valor}mg"
                elif 'g' in patron:
                    return f"{valor}g"
                elif 'mcg' in patron:
                    return f"{valor}mcg"
    
    return None

def extraer_forma_farmaceutica(texto):
    """
    Extrae la forma farmacéutica del texto.
    
    Args:
        texto (str): Texto del cual extraer forma
        
    Returns:
        set: Conjunto de formas farmacéuticas detectadas
    """
    if not texto:
        return set()
    
    texto_lower = texto.lower()
    formas_detectadas = set()
    
    # Mapeo de formas farmacéuticas y sus variantes
    formas_map = {
        'inyectable': ['inyectable', 'iny', 'inj', 'sol. iny', 'solucion inyectable'],
        'tableta': ['tableta', 'tabletas', 'tab', 'tabs', 'comprimidos', 'comps'], # comps añadido
        'capsula': ['capsula', 'capsulas', 'cap', 'caps', 'cápsula', 'cápsulas'],
        'solucion': ['solucion', 'solución', 'sol'],
        'jarabe': ['jarabe', 'suspension', 'suspensión', 'susp'], # susp añadido
        'crema': ['crema', 'gel', 'ungüento', 'pomada', 'unguento'], # unguento sin acento
        'ampolla': ['ampolla', 'ampollas', 'ampolleta', 'ampolletas', 'amptas'],
        'gotas': ['gotas', 'drops'],
    }
    
    for forma_base, variantes in formas_map.items():
        for variante in variantes:
            # Usar \b para asegurar que 'sol' no coincida con 'solucion' si 'solucion' ya está cubierta
            # o si se busca una palabra completa. Para variantes cortas como 'sol', 'tab', 'cap', es mejor
            # buscar como palabra completa si es posible, o asegurar que el orden de formas_map
            # no cause que una forma más específica sea opacada por una más general (ej. 'solucion' antes que 'sol').
            # Por ahora, la lógica de 'in' se mantiene como la original.
            if variante in texto_lower:
                formas_detectadas.add(forma_base)
                break # Una vez encontrada una variante de la forma_base, pasar a la siguiente forma_base
    
    return formas_detectadas

def normalizar_texto_simple(texto):
    """
    Normalización simple para comparación de palabras.
    """
    if not texto:
        return ""
    
    texto_norm = texto.lower().strip()
    # Eliminar caracteres especiales pero mantener espacios y números (importante para MG/ML)
    texto_norm = re.sub(r'[^\w\s/.-]', ' ', texto_norm) # Permitir / . - para concentraciones
    texto_norm = re.sub(r'\s+', ' ', texto_norm).strip()
    
    return texto_norm

def extraer_info_completa_tarjeta(tarjeta_elemento):
    """
    Extrae información completa de la tarjeta de Difarmer incluyendo principio activo.
    Prioriza selectores CSS específicos y luego recurre a análisis de texto si es necesario,
    intentando minimizar la extracción de datos incorrectos.
    
    Args:
        tarjeta_elemento: Elemento de la tarjeta del producto
        
    Returns:
        dict: Información completa extraída
    """
    info_completa = {
        'nombre_principal': '',
        'principio_activo': '',
        'laboratorio': '', # Añadido para completitud si se quisiera extraer
        'texto_completo': '',
        'nombres_para_comparar': []
    }
    
    try:
        texto_completo = tarjeta_elemento.text if tarjeta_elemento else ""
        info_completa['texto_completo'] = texto_completo
        
        logger.info(f"📋 Extrayendo info completa de tarjeta:")
        # logger.info(f"   Texto completo: {texto_completo}") # Puede ser muy verboso

        # --- MÉTODO 1: Extracción por CSS específicos (Priorizados) ---
        # El objetivo es ser lo más preciso posible para evitar "datos demas".
        
        # 1. NOMBRE PRINCIPAL
        # Selectores ordenados de más específico a más general.
        nombre_principal_selectors = [
            ".font-weight-bold.poppins.ml-2",  # Observado en imagen como específico para nombre
            ".font-weight-bold.font-poppins",  # Usado en tu script anterior
            ".font-weight-bold"                # Más general
        ]
        nombre_encontrado = False
        for selector in nombre_principal_selectors:
            try:
                elementos_nombre = tarjeta_elemento.find_elements(By.CSS_SELECTOR, selector)
                for elem in elementos_nombre:
                    if elem.is_displayed() and elem.text.strip():
                        texto_limpio = elem.text.strip()
                        # Condiciones para validar que es un nombre de producto probable
                        if (len(texto_limpio) > 10 and  # Generalmente los nombres son más largos
                            not '$' in texto_limpio and 
                            not texto_limpio.isdigit() and
                            "laboratorio:" not in texto_limpio.lower() and # Evitar que se cuele el lab
                            "principio activo:" not in texto_limpio.lower() and # Evitar que se cuele etiqueta de p.a.
                            "existencia:" not in texto_limpio.lower() and
                            "colectivo:" not in texto_limpio.lower()):
                            info_completa['nombre_principal'] = texto_limpio
                            if texto_limpio not in info_completa['nombres_para_comparar']:
                                info_completa['nombres_para_comparar'].append(texto_limpio)
                            logger.info(f"✅ Nombre principal extraído con '{selector}': '{texto_limpio}'")
                            nombre_encontrado = True
                            break # Tomar el primer elemento válido
            except Exception: # Ignorar errores de selector no encontrado y continuar
                pass
            if nombre_encontrado:
                break # Salir del bucle de selectores si ya se encontró

        # 2. PRINCIPIO ACTIVO
        # Selectores ordenados de más específico a más general.
        principio_activo_selectors = [
            ".font-weight-bolder.ml-2",  # Observado en imagen como específico para p.a.
            ".font-weight-bolder"        # Más general
        ]
        principio_encontrado = False
        for selector in principio_activo_selectors:
            try:
                elementos_principio = tarjeta_elemento.find_elements(By.CSS_SELECTOR, selector)
                for elem in elementos_principio:
                    if elem.is_displayed() and elem.text.strip():
                        texto_limpio = elem.text.strip()
                        # Condiciones para validar que es un principio activo probable
                        if (len(texto_limpio) > 2 and
                            texto_limpio.lower() != info_completa.get('nombre_principal', '').lower() and # No debe ser igual al nombre principal
                            not '$' in texto_limpio and 
                            not re.match(r'^\d+$', texto_limpio) and # No ser solo números
                            not ':' in texto_limpio and # Evitar etiquetas como "Laboratorio:"
                            "laboratorio:" not in texto_limpio.lower() and 
                            "existencia:" not in texto_limpio.lower() and
                            not any(keyword in texto_limpio.lower() for keyword in ['pzas', 'colectivo', 'precio', 'detalle', 'añadir', 'sol.', 'iny.'])
                            ):
                            info_completa['principio_activo'] = texto_limpio
                            if texto_limpio not in info_completa['nombres_para_comparar']:
                                info_completa['nombres_para_comparar'].append(texto_limpio)
                            logger.info(f"✅ Principio activo extraído con '{selector}': '{texto_limpio}'")
                            principio_encontrado = True
                            break # Tomar el primer elemento válido
            except Exception:
                pass
            if principio_encontrado:
                break

        # (Opcional) 3. LABORATORIO (si fuera necesario, con lógica similar)
        # ...

        # --- MÉTODO 2: Análisis de líneas de texto si el Método 1 no fue completamente exitoso ---
        if not info_completa['nombre_principal'] or not info_completa['principio_activo']:
            logger.info("ℹ️ Método 1 no extrajo toda la info, recurriendo a análisis de líneas del texto completo.")
            lineas = texto_completo.split('\n')
            
            posible_nombre_linea = ""
            posible_principio_linea = ""

            for i, linea in enumerate(lineas):
                linea_limpia = linea.strip()
                if not linea_limpia or len(linea_limpia) < 3: # Ignorar líneas muy cortas o vacías
                    continue
                
                # logger.info(f"   Línea {i} (M2): '{linea_limpia}'")

                # Evitar líneas que son claramente no nombres/principios (precios, existencia, etc.)
                if any(stop_word in linea_limpia.lower() for stop_word in ['$', 'precio', 'existencia', 'león', 'cedis', 'colectivo', 'laboratorio:', 'piezas', 'pzas', 'añadir al carrito', 'detalle de producto']):
                    continue

                # Intentar identificar nombre principal
                if not info_completa['nombre_principal'] and len(linea_limpia) > 10 and re.search(r'(?:MG|ML|TAB|CAP|SOL|INY|G\b|UI\b)', linea_limpia.upper()):
                    # Considerar si es una línea que parece un nombre de producto completo
                    if len(linea_limpia.split()) > 2 : # Al menos unas cuantas palabras
                         posible_nombre_linea = linea_limpia

                # Intentar identificar principio activo (suele ser más corto, una o dos palabras)
                elif not info_completa['principio_activo'] and (3 <= len(linea_limpia) <= 30) and re.match(r'^[a-zA-ZáéíóúÁÉÍÓÚñÑ\s]+$', linea_limpia) and not re.search(r'\d', linea_limpia):
                    if linea_limpia.lower() != posible_nombre_linea.lower(): # No ser igual al nombre ya encontrado
                        posible_principio_linea = linea_limpia
            
            if not info_completa['nombre_principal'] and posible_nombre_linea:
                info_completa['nombre_principal'] = posible_nombre_linea
                if posible_nombre_linea not in info_completa['nombres_para_comparar']:
                    info_completa['nombres_para_comparar'].append(posible_nombre_linea)
                logger.info(f"✅ Nombre principal (línea M2): '{posible_nombre_linea}'")

            if not info_completa['principio_activo'] and posible_principio_linea:
                # Asegurarse que el principio activo de línea no sea parte del nombre principal ya extraído
                if not info_completa['nombre_principal'] or (info_completa['nombre_principal'] and posible_principio_linea.lower() not in info_completa['nombre_principal'].lower()):
                    info_completa['principio_activo'] = posible_principio_linea
                    if posible_principio_linea not in info_completa['nombres_para_comparar']:
                        info_completa['nombres_para_comparar'].append(posible_principio_linea)
                    logger.info(f"✅ Principio activo (línea M2): '{posible_principio_linea}'")


        # --- MÉTODO 3: Fallback - usar líneas significativas si aún no hay nada para comparar ---
        # Este método es más propenso a "datos demas" si los anteriores fallan mucho.
        if not info_completa['nombres_para_comparar'] and texto_completo:
            logger.info("🔄 Método 1 y 2 no encontraron nada para comparar, usando fallback de líneas significativas.")
            lineas_significativas = []
            for linea in texto_completo.split('\n'):
                linea_limpia = linea.strip()
                # Filtro básico para líneas que podrían ser nombres o principios activos
                if (linea_limpia and 
                    len(linea_limpia) > 3 and # Al menos 4 caracteres
                    not '$' in linea_limpia and
                    not linea_limpia.isdigit() and
                    not any(stop_word in linea_limpia.lower() for stop_word in ['león:', 'cedis:', 'existencia:', 'laboratorio:', 'colectivo:', 'mi precio:'])
                    ):
                    lineas_significativas.append(linea_limpia)
            
            # Tomar las primeras N líneas significativas, evitando duplicados
            for sig_linea in lineas_significativas[:2]: # Tomar hasta 2 líneas significativas como máximo
                if sig_linea not in info_completa['nombres_para_comparar']:
                    info_completa['nombres_para_comparar'].append(sig_linea)
            logger.info(f"🔄 Fallback M3 - líneas para comparar: {info_completa['nombres_para_comparar']}")
            # Intentar asignar a nombre_principal y principio_activo si aún están vacíos
            if not info_completa['nombre_principal'] and len(info_completa['nombres_para_comparar']) > 0:
                info_completa['nombre_principal'] = info_completa['nombres_para_comparar'][0]
            if not info_completa['principio_activo'] and len(info_completa['nombres_para_comparar']) > 1:
                 if info_completa['nombres_para_comparar'][1] != info_completa['nombre_principal']:
                    info_completa['principio_activo'] = info_completa['nombres_para_comparar'][1]


        logger.info(f"📊 EXTRACCIÓN FINALIZADA:")
        logger.info(f"  Nombre principal: '{info_completa['nombre_principal']}'")
        logger.info(f"  Principio activo: '{info_completa['principio_activo']}'")
        logger.info(f"  Nombres para comparar ({len(info_completa['nombres_para_comparar'])}): {list(set(info_completa['nombres_para_comparar']))}") # Mostrar únicos

        return info_completa
        
    except Exception as e:
        logger.error(f"❌ Error general extrayendo info completa de tarjeta: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return info_completa


def calcular_similitud_individual(busqueda, texto_comparar):
    """
    Calcula similitud entre búsqueda y un texto específico.
    
    Args:
        busqueda (str): Término buscado por el usuario  
        texto_comparar (str): Texto individual a comparar
        
    Returns:
        float: Puntuación de similitud (0.0 a 1.0)
    """
    if not busqueda or not texto_comparar:
        return 0.0
    
    # logger.info(f"🔬 Calculando similitud individual:")
    # logger.info(f"   Búsqueda: '{busqueda}'")
    # logger.info(f"   Comparar: '{texto_comparar}'")
    
    puntuacion_total = 0.0
    
    # ✅ 1. COMPARAR CONCENTRACIONES (peso: 40%)
    conc_busqueda = extraer_concentracion(busqueda)
    conc_texto = extraer_concentracion(texto_comparar)
    
    puntuacion_concentracion = 0.0
    if conc_busqueda and conc_texto:
        if conc_busqueda == conc_texto:
            puntuacion_concentracion = 1.0
            # logger.info(f"✅ CONCENTRACIONES IDÉNTICAS: {conc_busqueda}")
        else:
            nums_busq = re.findall(r'\d+(?:\.\d+)?', conc_busqueda)
            nums_texto = re.findall(r'\d+(?:\.\d+)?', conc_texto)
            if nums_busq and nums_texto and nums_busq[0] == nums_texto[0]:
                puntuacion_concentracion = 0.7 # Coincidencia numérica parcial
                # logger.info(f"✅ VALORES NUMÉRICOS DE CONCENTRACIÓN COINCIDEN: {nums_busq[0]}")
    elif not conc_busqueda and not conc_texto: # Ninguno especifica concentración
        puntuacion_concentracion = 0.5  # Neutral si ninguno tiene info de concentración
    elif conc_busqueda and not conc_texto: # Búsqueda tiene, texto no
        puntuacion_concentracion = 0.2 # Penalización leve
    elif not conc_busqueda and conc_texto: # Texto tiene, búsqueda no
        puntuacion_concentracion = 0.3 # Penalización leve (es mejor si el producto lo especifica)
    else: # Uno tiene y el otro no, y no coinciden
        puntuacion_concentracion = 0.0
    
    puntuacion_total += puntuacion_concentracion * 0.40
    
    # ✅ 2. COMPARAR FORMAS FARMACÉUTICAS (peso: 30%)
    formas_busqueda = extraer_forma_farmaceutica(busqueda)
    formas_texto = extraer_forma_farmaceutica(texto_comparar)
    
    puntuacion_forma = 0.0
    if formas_busqueda and formas_texto:
        coincidencias_forma = formas_busqueda.intersection(formas_texto)
        if coincidencias_forma:
            # Puntuación basada en Jaccard Index
            puntuacion_forma = len(coincidencias_forma) / len(formas_busqueda.union(formas_texto))
            # logger.info(f"✅ FORMAS COINCIDENTES: {coincidencias_forma}, Puntuación: {puntuacion_forma:.2f}")
    elif not formas_busqueda and not formas_texto: # Ninguno especifica forma
        puntuacion_forma = 0.5  # Neutral
    elif formas_busqueda and not formas_texto: # Búsqueda tiene, texto no
        puntuacion_forma = 0.2 # Penalización
    elif not formas_busqueda and formas_texto: # Texto tiene, búsqueda no
        puntuacion_forma = 0.3 # Penalización
    else: # Uno tiene y el otro no, y no coinciden
        puntuacion_forma = 0.0
    
    puntuacion_total += puntuacion_forma * 0.30
    
    # ✅ 3. COMPARAR PALABRAS DEL NOMBRE (peso: 30%)
    busq_norm_orig = normalizar_texto_simple(busqueda)
    texto_norm_orig = normalizar_texto_simple(texto_comparar)
    
    busq_norm_clean = busq_norm_orig
    texto_norm_clean = texto_norm_orig

    if conc_busqueda: # Remover concentración de la búsqueda para comparar nombres
        busq_norm_clean = busq_norm_clean.replace(conc_busqueda.lower(), "").strip()
    if conc_texto: # Remover concentración del texto para comparar nombres
        texto_norm_clean = texto_norm_clean.replace(conc_texto.lower(), "").strip()
    
    # Eliminar palabras comunes de formas farmacéuticas para la comparación de nombres
    palabras_forma_comunes = ['sol', 'iny', 'tabletas', 'tab', 'caps', 'mg', 'ml', 'amptas', 'con', 'c', 'solucion', 'inyectable', 'comprimidos']
    
    palabras_busq = [p for p in busq_norm_clean.split() if p and p not in palabras_forma_comunes and len(p) > 1]
    palabras_texto = [p for p in texto_norm_clean.split() if p and p not in palabras_forma_comunes and len(p) > 1]
    
    puntuacion_nombre = 0.0
    if palabras_busq and palabras_texto:
        palabras_busq_set = set(palabras_busq)
        palabras_texto_set = set(palabras_texto)
        
        coincidencias_nombre = palabras_busq_set.intersection(palabras_texto_set)
        if coincidencias_nombre:
            # Jaccard para nombres
            puntuacion_nombre = len(coincidencias_nombre) / len(palabras_busq_set.union(palabras_texto_set))
            # logger.info(f"✅ PALABRAS COINCIDENTES EN NOMBRE: {coincidencias_nombre}, Puntuación: {puntuacion_nombre:.2f}")
        
        # Coincidencia parcial si no hay total, o para aumentar puntuación
        if not coincidencias_nombre or puntuacion_nombre < 0.5:
            partial_score = 0
            for p_busq in palabras_busq_set:
                for p_texto in palabras_texto_set:
                    if len(p_busq) >= 3 and len(p_texto) >=3: # Evitar coincidencias triviales de subcadenas cortas
                        if p_busq in p_texto or p_texto in p_busq:
                            partial_score += 0.1 # Pequeño bono por cada coincidencia parcial relevante
            puntuacion_nombre += min(partial_score, 0.3) # Limitar bono de coincidencia parcial

    elif not palabras_busq and not palabras_texto: # Si ambos nombres quedan vacíos tras limpiar (ej. solo son "500mg TAB")
        puntuacion_nombre = 0.5 # Neutral
    else: # Uno tiene palabras y el otro no
        puntuacion_nombre = 0.1 # Penalización alta

    puntuacion_nombre = min(puntuacion_nombre, 1.0) # Asegurar que no exceda 1.0
    puntuacion_total += puntuacion_nombre * 0.30
    
    # ✅ BONIFICACIONES ESPECIALES
    # Bonificación por coincidencia exacta del texto original (después de normalización simple)
    # Esto es útil si la búsqueda es por principio activo y coincide exactamente.
    if busq_norm_orig == texto_norm_orig and len(busq_norm_orig)>2 :
        puntuacion_total += 0.20 
        # logger.info(f"🎯 BONIFICACIÓN Coincidencia Exacta Normalizada: +0.20")

    # Bonificación si concentración Y forma coinciden bien
    if puntuacion_concentracion >= 0.7 and puntuacion_forma >= 0.7:
        puntuacion_total += 0.15
        # logger.info(f"🎯 BONIFICACIÓN Concentración + Forma: +0.15")
    
    # Bonificación por coincidencia al inicio del texto (más peso si la búsqueda es corta)
    if len(busq_norm_clean) > 2 and len(texto_norm_clean) > len(busq_norm_clean):
        if texto_norm_clean.startswith(busq_norm_clean):
            puntuacion_total += 0.1
            # logger.info(f"🎯 BONIFICACIÓN Inicio de Texto: +0.10")
    
    puntuacion_final = max(0.0, min(puntuacion_total, 1.0)) # Asegurar que esté entre 0 y 1
    
    # logger.info(f"📊 Similitud individual final: {puntuacion_final:.3f} (B: '{busqueda}', T: '{texto_comparar}')")
    
    return puntuacion_final

def calcular_similitud_producto_mejorada(busqueda, info_completa_tarjeta):
    """
    Calcula similitud comparando búsqueda contra TODOS los datos de la tarjeta:
    - Nombre principal 
    - Principio activo
    - Cualquier otro texto relevante de 'nombres_para_comparar'
    
    Toma la MEJOR similitud encontrada.
    """
    if not busqueda or not info_completa_tarjeta.get('nombres_para_comparar'):
        logger.info("ℹ️ No hay búsqueda o nombres para comparar, similitud = 0.")
        return 0.0
    
    nombres_a_evaluar = list(set(info_completa_tarjeta['nombres_para_comparar'])) # Usar solo únicos
    if not nombres_a_evaluar:
        logger.info("ℹ️ Lista 'nombres_para_comparar' está vacía tras eliminar duplicados, similitud = 0.")
        return 0.0

    logger.info(f"🔬 SIMILITUD MEJORADA (comparación múltiple):")
    logger.info(f"  Búsqueda: '{busqueda}'")
    logger.info(f"  Textos de tarjeta a comparar: {nombres_a_evaluar}")
    
    mejor_similitud = 0.0
    mejor_coincidencia_texto = ""
    
    for texto_comparar in nombres_a_evaluar:
        if not texto_comparar: # Doble check
            continue
            
        similitud_actual = calcular_similitud_individual(busqueda, texto_comparar)
        logger.info(f"    vs '{texto_comparar}' -> Similitud: {similitud_actual:.3f}")
        
        if similitud_actual > mejor_similitud:
            mejor_similitud = similitud_actual
            mejor_coincidencia_texto = texto_comparar
    
    logger.info(f"🏆 MEJOR SIMILITUD ENCONTRADA: {mejor_similitud:.3f} (con texto: '{mejor_coincidencia_texto}')")
    
    # Considerar un boost si la búsqueda coincide con el principio activo explícitamente
    pa_extraido = info_completa_tarjeta.get('principio_activo', '').strip()
    if pa_extraido and normalizar_texto_simple(busqueda) == normalizar_texto_simple(pa_extraido):
        if mejor_similitud < 0.85: # Si la similitud ya es alta, no necesita tanto boost
             logger.info(f"🎯 Coincidencia directa con Principio Activo '{pa_extraido}', aplicando posible boost.")
             mejor_similitud = max(mejor_similitud, 0.75) # Asegurar una buena puntuación si es el P.A.
             mejor_similitud = min(mejor_similitud + 0.1, 1.0) # Pequeño boost adicional

    return mejor_similitud


def buscar_producto(driver, nombre_producto):
    """
    Busca un producto en el sitio, extrae información detallada de la primera tarjeta relevante,
    y calcula similitud para decidir si coincide con la búsqueda.
    """
    if not driver:
        logger.error("❌ No se proporcionó un navegador (driver) válido.")
        return False
    
    try:
        logger.info(f"🔍 Iniciando búsqueda del producto: '{nombre_producto}'")
        
        search_field = None
        search_selectors = [
            "input[placeholder='¿Qué producto buscas?']",
            "input[type='search']",
            "input.form-control.SearchProduct" # Ejemplo de selector más específico si existe
        ]
        
        for selector in search_selectors:
            try:
                fields = driver.find_elements(By.CSS_SELECTOR, selector)
                # Encontrar el campo de búsqueda visible y habilitado
                for field_candidate in fields:
                    if field_candidate.is_displayed() and field_candidate.is_enabled():
                        search_field = field_candidate
                        logger.info(f"✅ Campo de búsqueda encontrado y listo con selector: {selector}")
                        break
                if search_field:
                    break
            except: # Ignorar errores si un selector no encuentra nada
                continue
        
        if not search_field:
            logger.error("❌ No se pudo encontrar el campo de búsqueda en la página.")
            driver.save_screenshot("error_sin_campo_busqueda.png")
            return False
            
        search_field.clear()
        search_field.send_keys(nombre_producto)
        search_field.send_keys(Keys.RETURN)
        logger.info(f"🚀 Búsqueda enviada para: '{nombre_producto}'")
        
        # Espera adaptable podría ser mejor, pero time.sleep es simple
        time.sleep(5) # Esperar a que carguen los resultados
        
        # driver.save_screenshot("resultados_busqueda_debug.png")
        # with open("resultados_busqueda_debug.html", "w", encoding="utf-8") as f:
        #     f.write(driver.page_source)

        # --- Lógica para encontrar y procesar tarjetas ---
        logger.info("🎯 Buscando tarjetas de productos en los resultados...")
        
        selectores_tarjetas = [
            "//div[contains(@class, 'card-body') and .//div[contains(@class, 'font-weight-bold')]]", # Tarjeta con cuerpo y nombre en negrita
            "//div[contains(., 'Laboratorio:') and contains(., 'Mi precio:')]", # Contiene info típica
            "//div[@class='product-item']", # Clase común para items de producto
            "//div[contains(@class, 'product-card')]",
            "//div[contains(@class, 'card') and .//img and .//*[contains(text(), '$')]]" # Tarjeta genérica con imagen y precio
        ]
        
        primera_tarjeta_elemento = None
        info_completa_tarjeta = {}
        tarjetas_encontradas_elementos = []

        for selector in selectores_tarjetas:
            try:
                elementos = driver.find_elements(By.XPATH, selector)
                # Filtrar solo elementos visibles y que parezcan tarjetas de producto individuales
                for elem in elementos:
                    if elem.is_displayed() and len(elem.text.split('\n')) > 2: # Más de 2 líneas de texto sugiere contenido
                        tarjetas_encontradas_elementos.append(elem)
                
                if tarjetas_encontradas_elementos:
                    logger.info(f"✅ {len(tarjetas_encontradas_elementos)} posibles tarjetas encontradas con selector: {selector}")
                    # Aquí podrías tener lógica para elegir la "mejor" tarjeta si hay varias.
                    # Por ahora, tomamos la primera de la lista combinada.
                    break # Usar el primer selector que devuelva algo
            except Exception as e:
                logger.warning(f"⚠️ Error buscando tarjetas con selector {selector}: {e}")
                continue
        
        if not tarjetas_encontradas_elementos:
            logger.warning(f"📉 No se encontraron elementos que parezcan tarjetas de producto para '{nombre_producto}'.")
            # Verificar explícitamente si el sitio muestra "No se encontraron resultados"
            no_results_elements = driver.find_elements(By.XPATH, "//*[contains(text(), 'No se encontraron resultados') or contains(text(), 'No hay productos para la búsqueda')]")
            for msg_elem in no_results_elements:
                if msg_elem.is_displayed():
                    logger.warning(f"❌ Confirmado: El sitio indica 'No se encontraron resultados' para '{nombre_producto}'.")
                    return False
            logger.warning(f"❌ No se encontraron tarjetas ni mensaje explícito de 'no resultados'. Asumiendo no encontrado.")
            return False

        # Procesar la primera tarjeta encontrada que parezca más completa o relevante
        # Esta lógica puede mejorarse para seleccionar la mejor tarjeta si hay múltiples.
        # Por simplicidad, se toma la primera de la lista de todas las encontradas.
        primera_tarjeta_elemento = tarjetas_encontradas_elementos[0]
        logger.info("ℹ️ Procesando la primera tarjeta de producto relevante encontrada.")
        info_completa_tarjeta = extraer_info_completa_tarjeta(primera_tarjeta_elemento)

        if not info_completa_tarjeta.get('nombres_para_comparar'):
            logger.warning(f"⚠️ No se pudo extraer información válida (nombres para comparar) de la tarjeta para '{nombre_producto}'.")
            # Re-confirmar mensaje de no resultados si la extracción falla
            no_results_elements = driver.find_elements(By.XPATH, "//*[contains(text(), 'No se encontraron resultados') or contains(text(), 'No hay productos para la búsqueda')]")
            for msg_elem in no_results_elements:
                if msg_elem.is_displayed():
                    logger.warning(f"❌ Confirmado (post-extracción fallida): El sitio indica 'No se encontraron resultados' para '{nombre_producto}'.")
                    return False
            return False
            
        # --- Calcular similitud ---
        similitud = calcular_similitud_producto_mejorada(nombre_producto, info_completa_tarjeta)
        umbral_similitud = 0.40 # Puedes ajustar este umbral
        
        logger.info(f"🧮 EVALUACIÓN DE SIMILITUD:")
        logger.info(f"  Búsqueda: '{nombre_producto}'")
        logger.info(f"  Mejor Similitud Calculada: {similitud:.3f} (Umbral: {umbral_similitud})")
        
        if similitud >= umbral_similitud:
            logger.info(f"✅ SIMILITUD ACEPTABLE. Producto encontrado y considerado coincidente.")
            # Aquí iría la lógica para hacer clic o interactuar con primera_tarjeta_elemento
            # ... (código de clic omitido para brevedad, pero seguiría la lógica de tu script original) ...
            # Ejemplo de cómo podrías intentar hacer clic:
            try:
                logger.info(f"🎯 Intentando hacer clic en la tarjeta del producto...")
                # driver.execute_script("arguments[0].scrollIntoView(true);", primera_tarjeta_elemento) # Asegurar visibilidad
                # time.sleep(0.5)
                # driver.execute_script("arguments[0].style.border='3px solid green'", primera_tarjeta_elemento) # Resaltar
                # time.sleep(0.5)
                
                # Buscar un enlace clickeable dentro de la tarjeta
                link_detalle = None
                try:
                    link_detalle = primera_tarjeta_elemento.find_element(By.XPATH, ".//a[contains(@href, 'detalle') or contains(@href, 'product')] | .//button[contains(text(), 'Detalle')]")
                except:
                    pass # No se encontró enlace específico
                
                if link_detalle and link_detalle.is_displayed() and link_detalle.is_enabled():
                    logger.info("🖱️ Haciendo clic en enlace/botón de detalle encontrado.")
                    link_detalle.click()
                else:
                    logger.info("🖱️ No se encontró enlace de detalle específico, haciendo clic en la tarjeta general.")
                    primera_tarjeta_elemento.click()

                time.sleep(3) # Esperar a que la nueva página cargue
                logger.info(f"✅ Clic realizado. URL actual: {driver.current_url}")
                return True # Indicar éxito
            except Exception as e_clic:
                logger.error(f"❌ Error al intentar hacer clic en el producto: {e_clic}")
                return False # Falló el clic o la navegación
        else:
            logger.warning(f"❌ SIMILITUD INSUFICIENTE. El producto encontrado no coincide lo suficiente con la búsqueda.")
            return False
            
    except Exception as e:
        logger.error(f"❌ Error mayor durante la búsqueda del producto: {e}")
        import traceback
        logger.error(traceback.format_exc())
        # driver.save_screenshot("error_busqueda_general_excepcion.png")
        return False


# --- Bloque para simular la ejecución (si ejecutas este archivo directamente) ---
if __name__ == '__main__':
    # Esta parte es para probar el script. Necesitarás configurar Selenium y un WebDriver.
    from selenium import webdriver
    from selenium.webdriver.chrome.service import Service as ChromeService
    from webdriver_manager.chrome import ChromeDriverManager

    logger.info("Iniciando script de prueba...")
    
    # Configura aquí el driver de Selenium (ej. ChromeDriver)
    # driver = webdriver.Chrome(service=ChromeService(ChromeDriverManager().install()))
    # driver.get("URL_DEL_SITIO_DE_PRUEBA_DIFARMER_O_SIMILAR") # Reemplazar con la URL real
    # time.sleep(3) # Esperar carga inicial

    # Ejemplo de cómo podrías usar la función buscar_producto:
    # (Necesitarías estar logueado si el sitio lo requiere antes de buscar)
    
    # producto_a_buscar = "INOTROPISA Sol. Iny. c/5 AMPTAS. 200 MG/ 5 ML"
    # producto_a_buscar = "Dopamina" 
    # producto_a_buscar = "Amoxicilina 500mg capsulas"

    # if driver: # Asegurarse que el driver se inicializó
    #     resultado_busqueda = buscar_producto(driver, producto_a_buscar)
    #     if resultado_busqueda:
    #         logger.info(f"🎉 Proceso de búsqueda para '{producto_a_buscar}' completado con éxito (producto encontrado y similar).")
    #     else:
    #         logger.info(f"😔 Proceso de búsqueda para '{producto_a_buscar}' finalizado (producto no encontrado o no similar).")
        
    #     time.sleep(2)
    #     driver.quit()
    #     logger.info("Navegador cerrado.")
    # else:
    #     logger.error("Driver no inicializado. Fin de la prueba.")

    # --- Pruebas de funciones individuales (sin Selenium) ---
    logger.info("\n--- Pruebas de extracción y similitud ---")
    
    # Simular tarjeta HTML (muy simplificado)
    class MockWebElement:
        def __init__(self, text_content, displayed=True, elements_map=None):
            self.text_content = text_content
            self.displayed = displayed
            self._elements_map = elements_map if elements_map else {}

        @property
        def text(self):
            return self.text_content

        def is_displayed(self):
            return self.displayed

        def find_elements(self, by, selector):
            # logger.debug(f"Mock find_elements: by={by}, selector='{selector}'")
            if selector in self._elements_map:
                # logger.debug(f"Mock returning: {self._elements_map[selector]} for selector '{selector}'")
                return self._elements_map[selector]
            return []

    # Ejemplo 1: INOTROPISA con Dopamina
    mock_card_text_inotropisa = """
    INOTROPISA Sol. Iny. c/5 AMPTAS. 200 MG/ 5 ML.
    Dopamina
    Laboratorio: PISA
    Colectivo: 88 pzas.
    Existencia: León: 10 Otros CEDIS: 107
    Mi precio: $192.65
    """
    # Simular que los selectores CSS encuentran los textos correctos
    # Esto es una simplificación; en Selenium real, la estructura HTML es más compleja.
    elements_map_inotropisa = {
        ".font-weight-bold.poppins.ml-2": [MockWebElement("INOTROPISA Sol. Iny. c/5 AMPTAS. 200 MG/ 5 ML.")],
        ".font-weight-bolder.ml-2": [MockWebElement("Dopamina")]
    }
    mock_tarjeta_inotropisa = MockWebElement(mock_card_text_inotropisa, elements_map=elements_map_inotropisa)
    
    logger.info("\n--- Tarjeta INOTROPISA ---")
    info_inotropisa = extraer_info_completa_tarjeta(mock_tarjeta_inotropisa)
    
    busqueda1 = "Inotropisa 200mg/5ml"
    logger.info(f"Calculando similitud para búsqueda: '{busqueda1}'")
    sim1 = calcular_similitud_producto_mejorada(busqueda1, info_inotropisa)
    logger.info(f"Similitud final para '{busqueda1}': {sim1:.3f}")

    busqueda2 = "Dopamina"
    logger.info(f"Calculando similitud para búsqueda: '{busqueda2}'")
    sim2 = calcular_similitud_producto_mejorada(busqueda2, info_inotropisa)
    logger.info(f"Similitud final para '{busqueda2}': {sim2:.3f} (Esperado > 0.4 si P.A. es 'Dopamina')")

    busqueda3 = "Paracetamol" # No debería coincidir
    logger.info(f"Calculando similitud para búsqueda: '{busqueda3}'")
    sim3 = calcular_similitud_producto_mejorada(busqueda3, info_inotropisa)
    logger.info(f"Similitud final para '{busqueda3}': {sim3:.3f}")

    # Ejemplo 2: Otro producto
    mock_card_text_amoxi = """
    AMOXICILINA 500MG 12 CAPSULAS
    Amoxicilina
    Laboratorio: GENERICO
    Mi precio: $50.00
    """
    elements_map_amoxi = {
        ".font-weight-bold": [MockWebElement("AMOXICILINA 500MG 12 CAPSULAS")], # Usando selector más general
        ".font-weight-bolder": [MockWebElement("Amoxicilina")]
    }
    mock_tarjeta_amoxi = MockWebElement(mock_card_text_amoxi, elements_map=elements_map_amoxi)
    logger.info("\n--- Tarjeta AMOXICILINA ---")
    info_amoxi = extraer_info_completa_tarjeta(mock_tarjeta_amoxi)

    busqueda4 = "amoxicilina 500mg caps"
    logger.info(f"Calculando similitud para búsqueda: '{busqueda4}'")
    sim4 = calcular_similitud_producto_mejorada(busqueda4, info_amoxi)
    logger.info(f"Similitud final para '{busqueda4}': {sim4:.3f}")

    busqueda5 = "Amoxicilina"
    logger.info(f"Calculando similitud para búsqueda: '{busqueda5}'")
    sim5 = calcular_similitud_producto_mejorada(busqueda5, info_amoxi)
    logger.info(f"Similitud final para '{busqueda5}': {sim5:.3f}")
