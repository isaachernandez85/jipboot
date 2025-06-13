#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Módulo principal para el scraper de NADRO - VERSIÓN COMPLETA CORREGIDA
Proporciona funcionalidad para buscar información de productos en el portal NADRO.
ACTUALIZADO: Con normalización específica para NADRO (nombre + cantidad separados).
REGLA NADRO: Nombre del principio activo + cantidad separada.
MODIFICADO: Con sistema de similitud 80%+ para validación más flexible.
✅ CORREGIDO: Limpieza completa de cookies, cache, localStorage y sessionStorage
"""

import time
import json
import random
import traceback
import logging
import re
import unicodedata
import tempfile
import shutil
from pathlib import Path

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Importar undetected_chromedriver solo si está disponible
try:
    import undetected_chromedriver as uc
    # Parche para evitar WinError 6 en el destructor de Chrome
    uc.Chrome.__del__ = lambda self: None
    UNDETECTED_AVAILABLE = True
except ImportError:
    logger.warning("undetected_chromedriver no está disponible. Se usará selenium estándar.")
    UNDETECTED_AVAILABLE = False
    # Importaciones alternativas si undetected_chromedriver no está disponible
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service
    from webdriver_manager.chrome import ChromeDriverManager

from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

# Configuración
USERNAME = "ventas@insumosjip.com"
PASSWORD = "Edu2014$"
MAIN_URL = "https://i22.nadro.mx/"  # URL base sin token de estado

# ===============================
# ✅ NUEVAS FUNCIONES DE LIMPIEZA DE SESIÓN
# ===============================

def crear_perfil_temporal():
    """
    Crea un perfil temporal de Chrome que se eliminará automáticamente
    """
    temp_dir = tempfile.mkdtemp(prefix="nadro_profile_")
    logger.info(f"🆕 Perfil temporal creado: {temp_dir}")
    return temp_dir

def limpiar_perfil_temporal(profile_path):
    """
    Elimina completamente el perfil temporal
    """
    try:
        if profile_path and Path(profile_path).exists():
            shutil.rmtree(profile_path)
            logger.info(f"🧹 Perfil temporal eliminado: {profile_path}")
    except Exception as e:
        logger.warning(f"⚠️ Error eliminando perfil temporal: {e}")

def limpiar_sesion_completa(driver):
    """
    ✅ FUNCIÓN NUEVA: Limpia COMPLETAMENTE todos los datos de sesión
    """
    try:
        logger.info("🧹 ===== INICIANDO LIMPIEZA COMPLETA DE SESIÓN =====")
        
        # 1. Limpiar todas las cookies
        logger.info("🍪 Limpiando cookies...")
        driver.delete_all_cookies()
        
        # 2. Limpiar localStorage
        logger.info("💾 Limpiando localStorage...")
        driver.execute_script("window.localStorage.clear();")
        
        # 3. Limpiar sessionStorage
        logger.info("🗂️ Limpiando sessionStorage...")
        driver.execute_script("window.sessionStorage.clear();")
        
        # 4. Limpiar indexedDB
        logger.info("🗄️ Limpiando indexedDB...")
        driver.execute_script("""
            if (window.indexedDB) {
                const deleteDatabase = (dbName) => {
                    return new Promise((resolve, reject) => {
                        const deleteReq = indexedDB.deleteDatabase(dbName);
                        deleteReq.onsuccess = () => resolve();
                        deleteReq.onerror = () => reject(deleteReq.error);
                    });
                };
                
                // Lista común de bases de datos que NADRO podría usar
                const commonDBs = ['NADRO', 'cache', 'session', 'user_data'];
                commonDBs.forEach(dbName => {
                    try { deleteDatabase(dbName); } catch(e) {}
                });
            }
        """)
        
        # 5. Limpiar cache del navegador (si es posible)
        logger.info("🗑️ Intentando limpiar cache...")
        try:
            # Navegar a página de configuración de Chrome para limpiar cache
            driver.execute_cdp_cmd('Network.clearBrowserCache', {})
            logger.info("✅ Cache limpiado via CDP")
        except Exception as e:
            logger.warning(f"⚠️ No se pudo limpiar cache via CDP: {e}")
        
        # 6. Forzar refresco completo
        logger.info("🔄 Refrescando navegador...")
        driver.refresh()
        time.sleep(2)
        
        logger.info("✅ ===== LIMPIEZA COMPLETA FINALIZADA =====")
        
    except Exception as e:
        logger.error(f"❌ Error durante limpieza de sesión: {e}")

def verificar_pagina_login_vs_principal(driver):
    """
    ✅ FUNCIÓN NUEVA: Verifica si estamos en login o en página principal
    """
    try:
        current_url = driver.current_url.lower()
        page_text = driver.page_source.lower()
        
        # Indicadores de página de login
        login_indicators = [
            "login" in current_url,
            "iniciar sesión" in page_text,
            "username" in page_text,
            "password" in page_text,
            "ingresar" in page_text
        ]
        
        # Indicadores de página principal/logueado
        main_indicators = [
            "logout" in page_text,
            "cerrar sesión" in page_text,
            "mi cuenta" in page_text,
            "buscar producto" in page_text,
            "carrito" in page_text
        ]
        
        en_login = any(login_indicators)
        en_principal = any(main_indicators)
        
        logger.info(f"📍 Estado de página: Login={en_login}, Principal={en_principal}")
        logger.info(f"📍 URL actual: {current_url}")
        
        return {
            "en_login": en_login,
            "en_principal": en_principal,
            "url": current_url
        }
        
    except Exception as e:
        logger.error(f"❌ Error verificando página: {e}")
        return {"en_login": False, "en_principal": False, "url": "unknown"}

# ===============================
# SISTEMA DE SIMILITUD 80%+ PARA NADRO
# ===============================

def normalizar_texto_nadro_similitud(texto):
    """Normalización específica para comparación en NADRO."""
    if not texto:
        return ""
    
    # Convertir a minúsculas y quitar acentos
    texto = texto.lower()
    texto = unicodedata.normalize('NFD', texto)
    texto = ''.join(c for c in texto if unicodedata.category(c) != 'Mn')
    
    # Normalizaciones específicas de farmacéuticos
    replacements = {
        'acetaminofen': 'paracetamol',
        'acetaminofén': 'paracetamol', 
        'miligramos': 'mg',
        'mililitros': 'ml',
        'microgramos': 'mcg',
        'gramos': 'g',
        'tabletas': 'tab',
        'comprimidos': 'tab',
        'capsulas': 'cap',
        'cápsulas': 'cap',
        'inyectable': 'iny',
        'solucion': 'sol',
        'solución': 'sol',
        'jarabe': 'jar'
    }
    
    for original, replacement in replacements.items():
        texto = re.sub(rf'\b{original}\b', replacement, texto)
    
    # Eliminar caracteres especiales excepto espacios y números
    texto = re.sub(r'[^\w\s]', ' ', texto)
    texto = re.sub(r'\s+', ' ', texto).strip()
    
    return texto

def extraer_componentes_nadro(texto_normalizado):
    """Extrae componentes clave del producto: nombre base + dosis."""
    # Extraer dosis (número + unidad)
    patron_dosis = r'(\d+(?:[.,]\d+)?)\s*(mg|ml|mcg|g|ui|l|tab|cap|iny|sol|jar)\b'
    match_dosis = re.search(patron_dosis, texto_normalizado)
    
    dosis_valor = ""
    dosis_unidad = ""
    if match_dosis:
        dosis_valor = match_dosis.group(1).replace(',', '.')
        dosis_unidad = match_dosis.group(2)
    
    # Remover la dosis del texto para obtener nombre base
    texto_sin_dosis = re.sub(patron_dosis, '', texto_normalizado).strip()
    texto_sin_dosis = re.sub(r'\s+', ' ', texto_sin_dosis)
    
    # Palabras clave (sin artículos ni palabras comunes)
    stop_words = {'el', 'la', 'los', 'las', 'un', 'una', 'de', 'del', 'y', 'con', 'por', 'para'}
    palabras = [p for p in texto_sin_dosis.split() if p not in stop_words and len(p) > 2]
    
    return {
        'nombre_base': texto_sin_dosis,
        'dosis_valor': dosis_valor,
        'dosis_unidad': dosis_unidad,
        'palabras_clave': set(palabras)
    }

def calcular_similitud_nadro_80(consulta_original, producto_encontrado):
    """Calcula similitud con umbral 80% para NADRO (más flexible)."""
    if not consulta_original or not producto_encontrado:
        return 0.0
    
    # Normalizar ambos textos
    consulta_norm = normalizar_texto_nadro_similitud(consulta_original)
    producto_norm = normalizar_texto_nadro_similitud(producto_encontrado)
    
    logger.debug(f"🔍 NADRO Similitud: '{consulta_original}' -> '{consulta_norm}'")
    logger.debug(f"🔍 NADRO Producto: '{producto_encontrado}' -> '{producto_norm}'")
    
    # Extraer componentes
    comp_consulta = extraer_componentes_nadro(consulta_norm)
    comp_producto = extraer_componentes_nadro(producto_norm)
    
    # CRITERIO 1: Coincidencia exacta de texto normalizado (peso: 40%)
    coincidencia_exacta = 0.0
    if consulta_norm == producto_norm:
        coincidencia_exacta = 1.0
        logger.debug(f"✅ NADRO: Coincidencia EXACTA de texto normalizado")
    elif consulta_norm in producto_norm or producto_norm in consulta_norm:
        coincidencia_exacta = 0.8
        logger.debug(f"✅ NADRO: Coincidencia PARCIAL de texto")
    
    # CRITERIO 2: Coincidencia de palabras clave (peso: 30%)
    palabras_consulta = comp_consulta['palabras_clave']
    palabras_producto = comp_producto['palabras_clave']
    
    if not palabras_consulta:
        coincidencia_palabras = 0.0
    else:
        palabras_comunes = palabras_consulta.intersection(palabras_producto)
        coincidencia_palabras = len(palabras_comunes) / len(palabras_consulta)
        
        # Bonus si TODAS las palabras coinciden
        if len(palabras_comunes) == len(palabras_consulta) == len(palabras_producto):
            coincidencia_palabras = 1.0
            logger.debug(f"✅ NADRO: TODAS las palabras clave coinciden: {palabras_comunes}")
        else:
            logger.debug(f"📝 NADRO: Palabras comunes: {palabras_comunes} de {palabras_consulta}")
    
    # CRITERIO 3: Coincidencia de dosis (peso: 30%) - MÁS FLEXIBLE PARA 80%
    coincidencia_dosis = 0.0
    
    consulta_tiene_dosis = bool(comp_consulta['dosis_valor'] and comp_consulta['dosis_unidad'])
    producto_tiene_dosis = bool(comp_producto['dosis_valor'] and comp_producto['dosis_unidad'])
    
    if consulta_tiene_dosis and producto_tiene_dosis:
        # Ambos tienen dosis: deben coincidir exactamente
        try:
            dosis_consulta = float(comp_consulta['dosis_valor'])
            dosis_producto = float(comp_producto['dosis_valor'])
            unidad_consulta = comp_consulta['dosis_unidad']
            unidad_producto = comp_producto['dosis_unidad']
            
            if dosis_consulta == dosis_producto and unidad_consulta == unidad_producto:
                coincidencia_dosis = 1.0
                logger.debug(f"✅ NADRO: Dosis EXACTA: {dosis_consulta}{unidad_consulta}")
            else:
                # ✅ CAMBIO: En lugar de 0.0, usar 0.3 para ser más flexible con 80%
                coincidencia_dosis = 0.3  # Penalización menos severa 
                logger.debug(f"⚠️ NADRO: Dosis DIFERENTE: {dosis_consulta}{unidad_consulta} vs {dosis_producto}{unidad_producto}")
        except ValueError:
            coincidencia_dosis = 0.2  # ✅ CAMBIO: Menos penalización por error de conversión
            logger.debug(f"❌ NADRO: Error convirtiendo dosis: '{comp_consulta['dosis_valor']}' vs '{comp_producto['dosis_valor']}'")
    
    elif not consulta_tiene_dosis and not producto_tiene_dosis:
        # Ninguno tiene dosis: OK, no penalizar
        coincidencia_dosis = 1.0
        logger.debug(f"✅ NADRO: Ninguno tiene dosis - OK")
    
    elif not consulta_tiene_dosis and producto_tiene_dosis:
        # Consulta sin dosis, producto con dosis: más neutral para 80%
        coincidencia_dosis = 0.8  # ✅ CAMBIO: Aumentado de 0.7 a 0.8
        logger.debug(f"⚠️ NADRO: Consulta sin dosis, producto con dosis: {comp_producto['dosis_valor']}{comp_producto['dosis_unidad']}")
    
    else:
        # Consulta con dosis, producto sin dosis: menos penalización para 80%
        coincidencia_dosis = 0.5  # ✅ CAMBIO: Aumentado de 0.3 a 0.5
        logger.debug(f"⚠️ NADRO: Consulta con dosis {comp_consulta['dosis_valor']}{comp_consulta['dosis_unidad']}, producto sin dosis")
    
    # CÁLCULO FINAL (pesos: 40% texto + 30% palabras + 30% dosis)
    similitud_final = (
        coincidencia_exacta * 0.40 +
        coincidencia_palabras * 0.30 +
        coincidencia_dosis * 0.30
    )
    
    # BONUS: Si el producto empieza igual que la consulta
    if producto_norm.startswith(consulta_norm) and len(consulta_norm) > 5:
        similitud_final += 0.05
        logger.debug(f"🎯 NADRO: Bonus por inicio coincidente")
    
    # ✅ NUEVO BONUS: Si la consulta está contenida en el producto (para 80%)
    if len(consulta_norm) > 3 and consulta_norm in producto_norm:
        similitud_final += 0.03
        logger.debug(f"🎯 NADRO: Bonus por consulta contenida en producto")
    
    # Asegurar que esté entre 0 y 1
    similitud_final = max(0.0, min(1.0, similitud_final))
    
    logger.debug(f"📊 NADRO SIMILITUD FINAL: {similitud_final:.3f} | Exacta:{coincidencia_exacta:.2f} Palabras:{coincidencia_palabras:.2f} Dosis:{coincidencia_dosis:.2f}")
    
    return similitud_final

def filtrar_productos_nadro_similitud(consulta_original, lista_productos, umbral=0.80):
    """Filtra productos de NADRO que superen 80% de similitud."""
    if not lista_productos:
        logger.warning(f"🔍 NADRO: Lista de productos vacía para '{consulta_original}'")
        return []
    
    resultados_validos = []
    
    logger.info(f"🔍 NADRO: Evaluando {len(lista_productos)} productos con umbral {umbral}")
    
    for i, producto in enumerate(lista_productos):
        nombre_producto = producto.get('nombre', '')
        
        if not nombre_producto:
            logger.warning(f"⚠️ NADRO: Producto #{i+1} sin nombre")
            continue
        
        similitud = calcular_similitud_nadro_80(consulta_original, nombre_producto)
        
        if similitud >= umbral:
            producto_con_similitud = producto.copy()
            producto_con_similitud['similitud_nadro'] = similitud
            resultados_validos.append(producto_con_similitud)
            
            logger.info(f"✅ NADRO #{i+1}: {similitud:.3f} - '{nombre_producto[:40]}...'")
        else:
            logger.info(f"❌ NADRO #{i+1}: {similitud:.3f} - '{nombre_producto[:40]}...' [RECHAZADO]")
    
    # Ordenar por similitud descendente
    resultados_validos.sort(key=lambda x: x.get('similitud_nadro', 0), reverse=True)
    
    logger.info(f"🏆 NADRO: {len(resultados_validos)} de {len(lista_productos)} productos superaron el umbral {umbral}")
    
    return resultados_validos

# ===============================
# FIN SISTEMA DE SIMILITUD
# ===============================

def normalizar_busqueda_nadro(producto_nombre):
    """
    Normaliza la búsqueda para NADRO: nombre + cantidad separados.
    Ejemplo: "diclofenaco inyectable 75 mg" → "diclofenaco 75 mg"
    
    Args:
        producto_nombre (str): Nombre completo del producto
        
    Returns:
        str: Nombre del principio activo + cantidad separados
    """
    if not producto_nombre:
        return producto_nombre
    
    # Convertir a minúsculas para procesamiento
    texto = producto_nombre.lower().strip()
    
    # Extraer cantidad (número + unidad)
    patron_cantidad = r'(\d+(?:\.\d+)?)\s*(mg|g|ml|mcg|ui|iu|%|cc|mgs)'
    match_cantidad = re.search(patron_cantidad, texto)
    cantidad = ""
    if match_cantidad:
        numero = match_cantidad.group(1)
        unidad = match_cantidad.group(2)
        # Normalizar unidad
        if unidad == 'mgs':
            unidad = 'mg'
        cantidad = f"{numero} {unidad}"
    
    # Extraer nombre del principio activo (primera palabra significativa)
    # Eliminar formas farmacéuticas comunes
    formas_farmaceuticas = [
        'inyectable', 'tabletas', 'tablets', 'cápsulas', 'capsulas', 
        'jarabe', 'solución', 'solucion', 'crema', 'gel', 'ungüento',
        'gotas', 'ampolletas', 'ampollas', 'suspensión', 'suspension',
        'comprimidos', 'pastillas', 'tabs', 'cap', 'sol', 'iny',
        'ampolla', 'vial', 'frasco', 'sobre', 'tubo'
    ]
    
    # Dividir en palabras
    palabras = texto.split()
    palabras_filtradas = []
    
    for palabra in palabras:
        # Saltar números y unidades ya procesados
        if re.match(r'\d+(?:\.\d+)?', palabra) or palabra in ['mg', 'g', 'ml', 'mcg', 'ui', 'iu', '%', 'cc', 'mgs']:
            continue
        # Saltar números con unidades pegadas (ej: "75mg")
        if re.match(r'\d+(?:\.\d+)?(mg|g|ml|mcg|ui|iu|%|cc|mgs)', palabra):
            continue
        # Saltar formas farmacéuticas
        if palabra in formas_farmaceuticas:
            continue
        # Mantener palabras del nombre
        palabras_filtradas.append(palabra)
    
    # Tomar las primeras 1-2 palabras del nombre (principio activo)
    if palabras_filtradas:
        # Si solo hay una palabra, usarla
        if len(palabras_filtradas) == 1:
            nombre = palabras_filtradas[0]
        else:
            # Si hay más palabras, tomar las primeras 2 para nombres compuestos
            nombre = ' '.join(palabras_filtradas[:2])
    else:
        # Si no queda nada, usar la primera palabra original
        nombre = producto_nombre.split()[0] if producto_nombre.split() else producto_nombre
    
    # Combinar nombre + cantidad
    if cantidad:
        resultado = f"{nombre} {cantidad}"
    else:
        resultado = nombre
    
    logger.info(f"[NADRO] Normalización: '{producto_nombre}' → '{resultado}'")
    return resultado

def random_delay(min_seconds=1.0, max_seconds=3.0):
    """Genera un retraso aleatorio para simular comportamiento humano"""
    delay = random.uniform(min_seconds, max_seconds)
    time.sleep(delay)
    return delay

def safe_driver_quit(driver, profile_path):
    """
    ✅ FUNCIÓN MEJORADA: Cierra navegador y limpia perfil temporal
    """
    try:
        if driver:
            # Última limpieza antes de cerrar
            logger.info("🧹 Limpieza final antes de cerrar...")
            try:
                limpiar_sesion_completa(driver)
            except:
                pass
            
            # Cerrar navegador
            driver.quit()
            logger.info("✅ Navegador cerrado")
            
        # Esperar un momento para que se liberen archivos
        time.sleep(2)
        
        # Limpiar perfil temporal
        limpiar_perfil_temporal(profile_path)
        
    except Exception as e:
        logger.error(f"❌ Error al cerrar navegador: {e}")
        # Intento alternativo para cerrar procesos
        try:
            import os
            if os.name == 'nt':  # Windows
                os.system("taskkill /f /im chromedriver.exe 2>nul")
                os.system("taskkill /f /im chrome.exe 2>nul")
            else:  # Linux/Mac
                os.system("pkill -f chromedriver 2>/dev/null")
                os.system("pkill -f chrome 2>/dev/null")
        except:
            pass

def inicializar_navegador_limpio(headless=True):
    """
    ✅ FUNCIÓN MEJORADA: Inicializa navegador con sesión completamente limpia
    """
    # Crear perfil temporal único para cada ejecución
    profile_path = crear_perfil_temporal()
    
    if UNDETECTED_AVAILABLE:
        try:
            logger.info("🔧 Iniciando navegador no detectable CON PERFIL LIMPIO...")
            
            options = uc.ChromeOptions()
            
            # ✅ CRÍTICO: Usar perfil temporal
            options.add_argument(f"--user-data-dir={profile_path}")
            
            # ✅ CRÍTICO: Deshabilitar persistencia de datos
            options.add_argument("--disable-background-networking")
            options.add_argument("--disable-sync")
            options.add_argument("--disable-translate")
            options.add_argument("--disable-ipc-flooding-protection")
            
            # ✅ CRÍTICO: Modo incógnito para sesión limpia
            options.add_argument("--incognito")
            
            # Configuración anti-detección
            options.add_argument("--disable-blink-features=AutomationControlled")
            options.add_argument("--disable-extensions")
            options.add_argument("--disable-popup-blocking")
            options.add_argument("--disable-notifications")
            
            # Opciones para entorno headless
            if headless:
                options.add_argument("--headless=new")
                options.add_argument("--no-sandbox")
                options.add_argument("--disable-dev-shm-usage")
            
            # Tamaño de ventana aleatorio
            width = random.randint(1100, 1300)
            height = random.randint(700, 900)
            options.add_argument(f"--window-size={width},{height}")
            
            # User Agent aleatorio
            user_agents = [
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
            ]
            options.add_argument(f"--user-agent={random.choice(user_agents)}")
            
            # ✅ NUEVO: Configuraciones adicionales para limpieza
            options.add_argument("--disable-features=VizDisplayCompositor")
            options.add_argument("--disable-web-security")
            options.add_argument("--disable-features=TranslateUI")
            
            # Inicializar navegador
            driver = uc.Chrome(options=options)
            
            # ✅ CRÍTICO: Limpiar sesión inmediatamente después de inicializar
            time.sleep(1)
            limpiar_sesion_completa(driver)
            
            logger.info("✅ Navegador no detectable inicializado con sesión limpia")
            return driver, profile_path
            
        except Exception as e:
            logger.error(f"❌ Error al inicializar navegador no detectable: {e}")
            # Limpiar perfil si falló
            limpiar_perfil_temporal(profile_path)
            logger.info("Intentando con navegador estándar...")
    
    # Respaldo con Selenium estándar
    try:
        options = webdriver.ChromeOptions() if not UNDETECTED_AVAILABLE else Options()
        
        # ✅ CRÍTICO: Usar perfil temporal
        options.add_argument(f"--user-data-dir={profile_path}")
        
        # ✅ CRÍTICO: Modo incógnito
        options.add_argument("--incognito")
        
        if headless:
            options.add_argument("--headless=new")
        
        # Configuración para entorno sin interfaz gráfica
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--disable-notifications")
        
        # Anti-detección
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)
        
        # ✅ NUEVO: Deshabilitar persistencia
        options.add_argument("--disable-background-networking")
        options.add_argument("--disable-sync")
        
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        
        # JavaScript anti-detección
        driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
            "source": """
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
            """
        })
        
        # ✅ CRÍTICO: Limpiar sesión inmediatamente
        time.sleep(1)
        limpiar_sesion_completa(driver)
        
        logger.info("✅ Navegador estándar inicializado con sesión limpia")
        return driver, profile_path
        
    except Exception as e:
        logger.error(f"❌ Error al inicializar navegador estándar: {e}")
        limpiar_perfil_temporal(profile_path)
        return None, None

def buscar_producto(driver, nombre_producto):
    """
    Busca un producto en NADRO:
    CORREGIDO: Detecta el botón COMPRAR directamente en la lista de resultados
    ANTES de hacer clic en los productos.
    
    Args:
        driver: WebDriver con sesión iniciada
        nombre_producto: texto a buscar (YA NORMALIZADO)
        
    Returns:
        dict: Resultado de la búsqueda con información de productos
    """
    try:
        logger.info(f"Buscando producto NORMALIZADO: {nombre_producto}")
        screenshot_path = str(Path("debug_screenshots").joinpath("despues_login.png"))
        driver.save_screenshot(screenshot_path)
        time.sleep(5)  # asegurar carga de la página

        # --- 1) Encontrar el campo de búsqueda ---
        search_selectors = [
            "input[placeholder='Buscar...']",
            "input.vtex-styleguide-9-x-input",
            "div.vtex-store-components-3-x-searchBarContainer input",
            "input[type='text'][placeholder]",
            "div.vtex-search-2-x-searchBar input"
        ]
        search_field = None
        for selector in search_selectors:
            try:
                elems = driver.find_elements(By.CSS_SELECTOR, selector)
                for el in elems:
                    if el.is_displayed():
                        search_field = el
                        break
                if search_field:
                    break
            except:
                continue
        if not search_field:
            # intento genérico
            elems = driver.find_elements(By.CSS_SELECTOR, "input[type='text']")
            for el in elems:
                if el.is_displayed():
                    search_field = el
                    break
        if not search_field:
            screenshot_path = str(Path("debug_screenshots").joinpath("error_no_campo_busqueda.png"))
            driver.save_screenshot(screenshot_path)
            html_path = str(Path("debug_logs").joinpath("pagina_despues_login.html"))
            with open(html_path, "w", encoding="utf-8") as f:
                f.write(driver.page_source)
            return {"error": "No se pudo encontrar el campo de búsqueda", "productos": []}

        # --- 2) Limpiar y escribir el texto de búsqueda NORMALIZADO ---
        driver.execute_script("arguments[0].focus();", search_field)
        time.sleep(0.5)
        search_field.clear()
        time.sleep(0.5)
        for c in nombre_producto:
            search_field.send_keys(c)
            time.sleep(random.uniform(0.05, 0.2))
        time.sleep(1)
        search_field.send_keys(Keys.RETURN)

        # --- 3) Esperar resultados ---
        logger.info("Esperando resultados...")
        time.sleep(8)
        screenshot_path = str(Path("debug_screenshots").joinpath("resultados_busqueda.png"))
        driver.save_screenshot(screenshot_path)
        html_path = str(Path("debug_logs").joinpath("resultados_busqueda.html"))
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(driver.page_source)

        # --- 4) Detectar listado de productos ---
        product_selectors = [
            "div.vtex-search-result-3-x-galleryItem",
            "article.vtex-product-summary-2-x-element", 
            "div.vtex-product-summary-2-x-container",
            "div[data-testid='gallery-layout-item']"
        ]
        productos = []
        for sel in product_selectors:
            try:
                elems = driver.find_elements(By.CSS_SELECTOR, sel)
                if elems:
                    productos = elems
                    logger.info(f"Encontrados {len(elems)} productos con selector: {sel}")
                    break
            except:
                continue

        if not productos:
            return {"error": "No se pudieron identificar productos en los resultados", "productos": []}

        # --- NUEVA LÓGICA: PROCESAR DIRECTAMENTE EN LA LISTA (SIN HACER CLIC) ---
        logger.info(f"🎯 PROCESANDO {len(productos)} PRODUCTOS DIRECTAMENTE EN LA LISTA")
        resultados = []
        
        for i, prod in enumerate(productos[:10]):
            try:
                driver.execute_script("arguments[0].scrollIntoView({behavior:'smooth',block:'center'});", prod)
                time.sleep(0.5)
                info = {}

                logger.info(f"🔍 ===== PROCESANDO PRODUCTO #{i+1} EN LISTA =====")

                # ===== EXTRACCIÓN DE NOMBRE =====
                for sel in [".vtex-product-summary-2-x-productBrand","h3",".vtex-product-summary-2-x-productNameContainer"]:
                    try:
                        el = prod.find_element(By.CSS_SELECTOR, sel)
                        if el.text.strip():
                            info["nombre"] = el.text.strip()
                            logger.info(f"📝 Nombre encontrado: {info['nombre']}")
                            break
                    except:
                        pass

                # ===== EXTRACCIÓN DE PRECIO =====
                logger.info(f"💰 Extrayendo precio para producto {i+1}")
                
                precio_principal_selectors = [
                    ".vtex-product-price-1-x-sellingPrice",
                    ".vtex-store-components-3-x-price", 
                    ".nadro-nadro-components-1-x-priceContainer",
                    ".nadro-nadro-components-1-x-priceContainerOnline--product-pill",
                    ".price",
                    "*[class*='price']"
                ]
                
                for sel in precio_principal_selectors:
                    try:
                        els = prod.find_elements(By.CSS_SELECTOR, sel)
                        for el in els:
                            txt = el.text.strip()
                            if "$" in txt and any(c.isdigit() for c in txt):
                                info["precio_farmacia"] = txt
                                logger.info(f"✅ Precio extraído: {txt}")
                                break
                        if info.get("precio_farmacia"):
                            break
                    except:
                        pass

                # Si no encontramos precio con selectores específicos
                if not info.get("precio_farmacia"):
                    try:
                        all_elements = prod.find_elements(By.XPATH, ".//*[contains(text(), '$')]")
                        for el in all_elements:
                            txt = el.text.strip()
                            if "$" in txt and any(c.isdigit() for c in txt) and len(txt) < 20:
                                info["precio_farmacia"] = txt
                                logger.info(f"✅ Precio encontrado (genérico): {txt}")
                                break
                    except:
                        pass

                # ===== DETECCIÓN DE BOTÓN COMPRAR EN LA TARJETA =====
                logger.info(f"🎯 ===== DETECTANDO BOTÓN COMPRAR EN TARJETA #{i+1} =====")
                
                disponibilidad_detectada = False
                
                # MÉTODO 1: Buscar botones con texto "COMPRAR"
                try:
                    logger.info(f"🔍 Método 1: Buscando botones con texto COMPRAR")
                    
                    # Selectores específicos para botones COMPRAR
                    botones_comprar_selectors = [
                        "button:contains('COMPRAR')",
                        "button[class*='comprar']",
                        "button[class*='buy']",
                        "button[class*='add-to-cart']",
                        ".comprar-button",
                        ".buy-button",
                        ".add-to-cart-button"
                    ]
                    
                    for selector in botones_comprar_selectors:
                        try:
                            botones = prod.find_elements(By.CSS_SELECTOR, selector)
                            for boton in botones:
                                if boton.is_displayed():
                                    texto_boton = boton.text.strip().upper()
                                    if "COMPRAR" in texto_boton:
                                        disabled = boton.get_attribute("disabled")
                                        class_attr = boton.get_attribute("class") or ""
                                        
                                        logger.info(f"✅ BOTÓN COMPRAR ENCONTRADO!")
                                        logger.info(f"   📌 Texto: '{texto_boton}'")
                                        logger.info(f"   📌 Disabled: {disabled}")
                                        logger.info(f"   📌 Clases: {class_attr}")
                                        
                                        if not disabled and "disabled" not in class_attr.lower():
                                            info["existencia"] = "Disponible"
                                            logger.info(f"✅ PRODUCTO DISPONIBLE - Botón COMPRAR activo")
                                        else:
                                            info["existencia"] = "No disponible"  
                                            logger.info(f"❌ PRODUCTO NO DISPONIBLE - Botón COMPRAR deshabilitado")
                                        
                                        disponibilidad_detectada = True
                                        break
                            if disponibilidad_detectada:
                                break
                        except:
                            pass
                        
                    if disponibilidad_detectada:
                        logger.info(f"✅ Método 1 EXITOSO")
                    
                except Exception as e:
                    logger.error(f"Error en Método 1: {e}")

                # MÉTODO 2: Buscar por XPath más agresivo si Método 1 falló
                if not disponibilidad_detectada:
                    try:
                        logger.info(f"🔍 Método 2: XPath agresivo para COMPRAR")
                        
                        # XPath para buscar cualquier elemento que contenga "COMPRAR"
                        xpath_comprar = [
                            ".//button[contains(translate(text(), 'abcdefghijklmnopqrstuvwxyz', 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'), 'COMPRAR')]",
                            ".//*[contains(translate(text(), 'abcdefghijklmnopqrstuvwxyz', 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'), 'COMPRAR')]",
                            ".//button[contains(@class, 'comprar')]",
                            ".//button[contains(@class, 'buy')]"
                        ]
                        
                        for xpath in xpath_comprar:
                            elementos = prod.find_elements(By.XPATH, xpath)
                            for elem in elementos:
                                if elem.is_displayed():
                                    texto_elem = elem.text.strip().upper()
                                    tag_name = elem.tag_name.lower()
                                    
                                    if "COMPRAR" in texto_elem:
                                        logger.info(f"✅ ELEMENTO COMPRAR ENCONTRADO (XPath)!")
                                        logger.info(f"   📌 Tag: {tag_name}")
                                        logger.info(f"   📌 Texto: '{texto_elem}'")
                                        
                                        # Si es un botón, verificar si está habilitado
                                        if tag_name == "button":
                                            disabled = elem.get_attribute("disabled")
                                            if not disabled:
                                                info["existencia"] = "Disponible"
                                                logger.info(f"✅ PRODUCTO DISPONIBLE")
                                            else:
                                                info["existencia"] = "No disponible"
                                                logger.info(f"❌ PRODUCTO NO DISPONIBLE")
                                        else:
                                            # Si no es botón pero contiene COMPRAR, asumir disponible
                                            info["existencia"] = "Disponible"
                                            logger.info(f"✅ PRODUCTO DISPONIBLE (elemento no-botón)")
                                        
                                        disponibilidad_detectada = True
                                        break
                            if disponibilidad_detectada:
                                break
                                
                        if disponibilidad_detectada:
                            logger.info(f"✅ Método 2 EXITOSO")
                            
                    except Exception as e:
                        logger.error(f"Error en Método 2: {e}")

                # MÉTODO 3: Análisis de texto completo de la tarjeta
                if not disponibilidad_detectada:
                    try:
                        logger.info(f"🔍 Método 3: Análisis de texto completo")
                        
                        texto_completo = prod.text.upper()
                        logger.info(f"📄 Texto completo de tarjeta #{i+1}:")
                        logger.info(f"📄 {texto_completo}")
                        
                        if "COMPRAR" in texto_completo:
                            logger.info(f"✅ TEXTO 'COMPRAR' ENCONTRADO en la tarjeta")
                            
                            # Verificar si hay indicadores de "NO DISPONIBLE"
                            if any(indicador in texto_completo for indicador in ["NO DISPONIBLE", "AGOTADO", "SIN STOCK"]):
                                info["existencia"] = "No disponible"
                                logger.info(f"❌ PRODUCTO NO DISPONIBLE (texto negativo encontrado)")
                            else:
                                info["existencia"] = "Disponible" 
                                logger.info(f"✅ PRODUCTO DISPONIBLE (COMPRAR sin negativos)")
                            
                            disponibilidad_detectada = True
                        else:
                            logger.warning(f"❌ NO se encontró 'COMPRAR' en el texto de la tarjeta")
                            
                    except Exception as e:
                        logger.error(f"Error en Método 3: {e}")

                # MÉTODO 4: Buscar clases CSS que indiquen disponibilidad
                if not disponibilidad_detectada:
                    try:
                        logger.info(f"🔍 Método 4: Análisis de clases CSS de disponibilidad")
                        
                        # Buscar elementos con clases que indiquen disponibilidad
                        disponibilidad_classes = [
                            "[class*='available']",
                            "[class*='in-stock']", 
                            "[class*='comprar']",
                            "[class*='buy']",
                            "[class*='add-cart']"
                        ]
                        
                        for css_selector in disponibilidad_classes:
                            elementos = prod.find_elements(By.CSS_SELECTOR, css_selector)
                            for elem in elementos:
                                if elem.is_displayed():
                                    class_attr = elem.get_attribute("class") or ""
                                    logger.info(f"✅ Elemento con clase de disponibilidad encontrado: {class_attr}")
                                    
                                    # Si la clase no contiene "disabled" o "unavailable"
                                    if not any(neg in class_attr.lower() for neg in ["disabled", "unavailable", "out-of-stock"]):
                                        info["existencia"] = "Disponible"
                                        logger.info(f"✅ PRODUCTO DISPONIBLE (por clase CSS)")
                                        disponibilidad_detectada = True
                                        break
                            if disponibilidad_detectada:
                                break
                                
                    except Exception as e:
                        logger.error(f"Error en Método 4: {e}")

                # Si ningún método funcionó
                if not disponibilidad_detectada:
                    info["existencia"] = "Estado desconocido"
                    logger.error(f"❌ ¡TODOS LOS MÉTODOS FALLARON para producto #{i+1}!")
                    logger.error(f"❌ No se pudo determinar disponibilidad")
                    
                    # Guardar HTML de la tarjeta para debug
                    try:
                        html_tarjeta = prod.get_attribute("outerHTML")
                        debug_logs_dir = Path("debug_logs")
                        debug_logs_dir.mkdir(exist_ok=True)
                        with open(debug_logs_dir / f"tarjeta_{i+1}_html.html", "w", encoding="utf-8") as f:
                            f.write(html_tarjeta)
                        logger.error(f"💾 HTML de tarjeta guardado en debug_logs/tarjeta_{i+1}_html.html")
                    except Exception as save_error:
                        logger.error(f"Error guardando HTML: {save_error}")

                # Agregar producto a resultados si tiene información mínima
                if info.get("nombre"):
                    resultados.append(info)
                    logger.info(f"📋 RESULTADO FINAL Producto #{i+1}:")
                    logger.info(f"   📌 Nombre: {info['nombre']}")
                    logger.info(f"   📌 Precio: {info.get('precio_farmacia','N/D')}")
                    logger.info(f"   📌 Existencia: {info.get('existencia','N/D')}")
                else:
                    logger.warning(f"⚠️ Producto #{i+1} descartado - no tiene nombre")
                
                logger.info(f"🔚 ===== FIN PROCESAMIENTO PRODUCTO #{i+1} =====")

            except Exception as e:
                logger.error(f"❌ Error procesando producto {i+1}: {e}")
                import traceback
                logger.error(traceback.format_exc())

        if resultados:
            # ✅ APLICAR FILTRO DE SIMILITUD 80%+
            productos_filtrados = filtrar_productos_nadro_similitud(
                nombre_producto,  # nombre normalizado que ya se pasa a la función
                resultados,
                umbral=0.80
            )
            
            if productos_filtrados:
                logger.info(f"✅ NADRO FILTRADO: {len(productos_filtrados)} productos válidos de {len(resultados)} originales")
                return {"success": True, "productos": productos_filtrados}
            else:
                logger.warning(f"❌ NADRO: Ningún producto superó el umbral de 80% de similitud")
                # Opcional: Mostrar el mejor resultado aunque no supere el 80%
                if resultados:
                    mejor_resultado = max(resultados, key=lambda x: calcular_similitud_nadro_80(nombre_producto, x.get('nombre', '')))
                    similitud_mejor = calcular_similitud_nadro_80(nombre_producto, mejor_resultado.get('nombre', ''))
                    logger.info(f"💡 Mejor resultado disponible: {similitud_mejor:.3f} - '{mejor_resultado.get('nombre', '')[:50]}...'")
                
                return {"warning": f"No se encontraron productos con similitud >= 80% para '{nombre_producto}'", "productos": []}
        else:
            logger.warning(f"⚠️ No se pudieron procesar productos de la lista")
            return {"warning": "No se pudo extraer información de productos", "productos": []}

    except Exception as e:
        logger.error(f"Error durante la búsqueda de producto: {e}")
        traceback.print_exc()
        return {"error": str(e), "productos": []}

def login_and_search_limpio(producto):
    """
    ✅ FUNCIÓN PRINCIPAL MEJORADA: Login y búsqueda con sesión completamente limpia
    """
    driver = None
    profile_path = None
    
    try:
        # Inicializar navegador con perfil limpio
        driver, profile_path = inicializar_navegador_limpio(headless=True)
        if not driver:
            return {"error": "No se pudo inicializar el navegador", "productos": []}
        
        # Navegar a la página principal con delay aleatorio
        logger.info(f"🌐 Navegando a {MAIN_URL}...")
        driver.get(MAIN_URL)
        time.sleep(random.uniform(3, 5))
        
        # ✅ VERIFICAR ESTADO INICIAL
        estado_inicial = verificar_pagina_login_vs_principal(driver)
        
        if estado_inicial["en_principal"]:
            logger.warning("⚠️ Ya estamos en página principal sin login - algo raro")
            logger.warning("⚠️ Forzando limpieza adicional...")
            limpiar_sesion_completa(driver)
            driver.get(MAIN_URL)
            time.sleep(3)
            estado_inicial = verificar_pagina_login_vs_principal(driver)
        
        # Buscar enlace de login si no estamos ya en página de login
        if not estado_inicial["en_login"]:
            logger.info("🔍 Buscando enlace de login...")
            login_link_found = False
            
            login_selectors = [
                "a[href*='login']", 
                "a.vtex-login-2-x-button",
                "span:contains('Iniciar sesión')",
                "button:contains('Ingresar')",
                "a:contains('Iniciar sesión')",
                "span:contains('Login')"
            ]
            
            for selector in login_selectors:
                try:
                    elements = driver.find_elements(By.CSS_SELECTOR, selector)
                    for element in elements:
                        if element.is_displayed():
                            logger.info(f"🖱️ Enlace de login encontrado. Haciendo clic...")
                            element.click()
                            login_link_found = True
                            time.sleep(random.uniform(3, 5))
                            break
                    if login_link_found:
                        break
                except:
                    continue
            
            # Si no encontramos enlaces, usar URL directa
            if not login_link_found:
                logger.info("📍 No se encontró enlace. Navegando a URL de login directa...")
                driver.get("https://i22.nadro.mx/login")
                time.sleep(random.uniform(3, 5))
        
        # ✅ VERIFICAR QUE ESTAMOS EN LOGIN
        estado_login = verificar_pagina_login_vs_principal(driver)
        if not estado_login["en_login"]:
            # Captura para debug
            debug_dir = Path("debug_screenshots")
            debug_dir.mkdir(exist_ok=True)
            driver.save_screenshot(str(debug_dir / "no_esta_en_login.png"))
            
            logger.error("❌ No estamos en página de login después de intentar navegar")
            return {"error": "No se pudo acceder a la página de login", "productos": []}
        
        # Captura de página de login
        debug_dir = Path("debug_screenshots")
        debug_dir.mkdir(exist_ok=True)
        driver.save_screenshot(str(debug_dir / "pagina_login_limpia.png"))
        
        # PROCESO DE LOGIN con limpieza previa
        logger.info("🔐 Iniciando proceso de login con sesión limpia...")
        
        try:
            # Buscar campo de usuario
            logger.info("👤 Buscando campo de usuario...")
            username_field = WebDriverWait(driver, 15).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "input[type='text'], input[type='email'], #username, input[name='username']"))
            )
            
            # Escribir usuario con delays humanos
            logger.info(f"✍️ Ingresando usuario: {USERNAME}")
            username_field.clear()
            time.sleep(random.uniform(0.5, 1.5))
            
            for c in USERNAME:
                username_field.send_keys(c)
                time.sleep(random.uniform(0.1, 0.3))
            
            time.sleep(random.uniform(0.5, 1.5))
            
            # Buscar campo de contraseña
            logger.info("🔒 Buscando campo de contraseña...")
            password_field = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "input[type='password'], #password, input[name='password']"))
            )
            
            # Escribir contraseña
            logger.info("✍️ Ingresando contraseña...")
            password_field.clear()
            time.sleep(random.uniform(0.5, 1.5))
            
            for c in PASSWORD:
                password_field.send_keys(c)
                time.sleep(random.uniform(0.1, 0.3))
            
            time.sleep(random.uniform(1, 2))
            
            # Buscar y hacer clic en botón de login
            logger.info("🖱️ Buscando botón de login...")
            login_button = None
            
            button_selectors = [
                "button[type='submit']",
                "input[type='submit']",
                "button.login-button",
                "button:contains('Iniciar sesión')",
                "button:contains('Ingresar')",
                "button.btn-primary"
            ]
            
            for selector in button_selectors:
                try:
                    elements = driver.find_elements(By.CSS_SELECTOR, selector)
                    for element in elements:
                        if element.is_displayed():
                            login_button = element
                            break
                    if login_button:
                        break
                except:
                    continue
            
            # Enviar login
            if login_button:
                logger.info("🚀 Haciendo clic en botón de login...")
                login_button.click()
            else:
                logger.info("⌨️ No se encontró botón. Enviando con Enter...")
                password_field.send_keys(Keys.RETURN)
            
            # Esperar procesamiento de login
            logger.info("⏳ Procesando login...")
            time.sleep(random.uniform(8, 12))
            
            # Captura después del login
            driver.save_screenshot(str(debug_dir / "despues_login_limpio.png"))
            
            # ✅ VERIFICAR LOGIN EXITOSO
            estado_final = verificar_pagina_login_vs_principal(driver)
            
            if estado_final["en_principal"] or "login" not in estado_final["url"]:
                logger.info("✅ Login exitoso con sesión limpia. Procediendo con búsqueda...")
                
                # Realizar búsqueda del producto
                resultado = buscar_producto(driver, producto)
                return resultado
            else:
                logger.error("❌ Login fallido con sesión limpia")
                
                # Guardar HTML para análisis
                debug_logs_dir = Path("debug_logs")
                debug_logs_dir.mkdir(exist_ok=True)
                with open(debug_logs_dir / "login_fallido_limpio.html", "w", encoding="utf-8") as f:
                    f.write(driver.page_source)
                
                return {"error": "Login fallido después de limpiar sesión", "productos": []}
                
        except Exception as e:
            logger.error(f"❌ Error durante proceso de login limpio: {e}")
            driver.save_screenshot(str(debug_dir / "error_login_limpio.png"))
            return {"error": f"Error de login con sesión limpia: {str(e)}", "productos": []}
    
    except Exception as e:
        logger.error(f"❌ Error general en login_and_search_limpio: {e}")
        traceback.print_exc()
        return {"error": str(e), "productos": []}
    
    finally:
        # ✅ LIMPIEZA FINAL GARANTIZADA
        logger.info("🧹 Iniciando limpieza final...")
        safe_driver_quit(driver, profile_path)

def buscar_info_medicamento(nombre_medicamento, headless=True):
    """
    ✅ FUNCIÓN PRINCIPAL CORREGIDA: Con limpieza completa de sesión
    ACTUALIZADO: Con normalización específica para NADRO.
    MODIFICADO: Con sistema de similitud 80%+ integrado.
    
    Args:
        nombre_medicamento (str): Nombre del medicamento a buscar
        headless (bool): Si es True, el navegador se ejecuta en modo headless
        
    Returns:
        dict: Diccionario con la información del medicamento en formato compatible
    """
    try:
        logger.info(f"🚀 Iniciando búsqueda NADRO con sesión limpia: {nombre_medicamento}")
        
        # ✅ NUEVO: Normalizar búsqueda para NADRO
        nombre_normalizado = normalizar_busqueda_nadro(nombre_medicamento)
        
        # Crear directorios para debug
        Path("debug_screenshots").mkdir(exist_ok=True)
        Path("debug_logs").mkdir(exist_ok=True)
        
        # ✅ USAR FUNCIÓN DE LOGIN LIMPIA
        resultado = login_and_search_limpio(nombre_normalizado)
        
        # Si hay error, devolver un formato compatible con mensaje de error
        if "error" in resultado:
            return {
                "nombre": nombre_medicamento,
                "error": resultado["error"],
                "estado": "error",
                "fuente": "NADRO",
                "existencia": "0"
            }
        
        # Si hay advertencia pero sin productos
        if "warning" in resultado or not resultado.get("productos"):
            return {
                "nombre": nombre_medicamento,
                "mensaje": resultado.get("warning", "No se encontraron productos"),
                "estado": "no_encontrado",
                "fuente": "NADRO",
                "existencia": "0"
            }
        
        # Si hay productos, formatear el primero en formato compatible
        if resultado.get("productos"):
            primer_producto = resultado["productos"][0]
            
            # Crear un diccionario en formato compatible con el resto de scrapers
            info_producto = {
                "nombre": primer_producto.get("nombre", nombre_medicamento),
                "laboratorio": primer_producto.get("laboratorio", "No disponible"),
                "codigo_barras": primer_producto.get("codigo_barras", "No disponible"),
                "registro_sanitario": "No disponible",
                "url": "https://i22.nadro.mx/",
                "imagen": primer_producto.get("imagen", ""),
                "precio": primer_producto.get("precio_farmacia", primer_producto.get("precio_publico", "No disponible")),
                "existencia": "0",
                "fuente": "NADRO",
                "estado": "encontrado"
            }
            
            # ===== PROCESAMIENTO DE EXISTENCIA CORREGIDO PARA NADRO =====
            logger.info(f"🔄 Procesando existencia basada SOLO en botón COMPRAR")
            
            existencia_raw = primer_producto.get("existencia", "")
            if existencia_raw:
                existencia_lower = existencia_raw.lower()
                logger.info(f"🔍 Analizando estado de disponibilidad: '{existencia_raw}'")
                
                # LÓGICA PRINCIPAL: Solo botón COMPRAR indica disponibilidad real
                if "disponible" in existencia_lower:
                    # Esto viene del botón COMPRAR activo
                    info_producto["existencia"] = "Si"
                    logger.info(f"✅ Producto DISPONIBLE (botón COMPRAR encontrado): {existencia_raw}")
                elif "no disponible" in existencia_lower or "agotado" in existencia_lower:
                    # Esto viene cuando no hay botón COMPRAR
                    info_producto["existencia"] = "0"
                    logger.info(f"❌ Producto NO DISPONIBLE: {existencia_raw}")
                else:
                    # Cualquier otro texto (como "Entrega mañana") sin botón COMPRAR
                    # indica que no pudimos determinar disponibilidad correctamente
                    info_producto["existencia"] = "0"
                    logger.warning(f"⚠️ Estado ambiguo - probablemente faltó detectar botón COMPRAR: {existencia_raw}")
                    logger.warning(f"💡 NOTA: '{existencia_raw}' parece ser info de envío, no de disponibilidad")
            else:
                info_producto["existencia"] = "0"
                logger.info(f"⚠️ Sin información de existencia")
            
            # Si hay más productos, incluirlos como datos adicionales
            if len(resultado["productos"]) > 1:
                info_producto["productos_adicionales"] = resultado["productos"][1:]
                info_producto["total_productos"] = len(resultado["productos"])
            
            # Mostrar información de similitud si está disponible
            if 'similitud_nadro' in primer_producto:
                logger.info(f"🎯 NADRO: Producto seleccionado con similitud {primer_producto['similitud_nadro']:.3f}")
            
            logger.info(f"✅ Producto encontrado en NADRO (sesión limpia): {info_producto['nombre']} - Precio: {info_producto['precio']} - Existencia: {info_producto['existencia']}")
            return info_producto
        
        # Si llegamos aquí sin retornar, algo salió mal
        return {
            "nombre": nombre_medicamento,
            "mensaje": "No se pudo procesar la respuesta del servidor NADRO",
            "estado": "error",
            "fuente": "NADRO",
            "existencia": "0"
        }
        
    except Exception as e:
        logger.error(f"❌ Error general en buscar_info_medicamento: {e}")
        traceback.print_exc()
        return {
            "nombre": nombre_medicamento,
            "error": str(e),
            "estado": "error",
            "fuente": "NADRO",
            "existencia": "0"
        }

# Para ejecución directa como script independiente
if __name__ == "__main__":
    import sys
    import json
    
    print("=== Sistema de Búsqueda de Medicamentos en NADRO ===")
    print("=== CON LIMPIEZA COMPLETA DE SESIÓN + FILTRO SIMILITUD 80%+ ===")
    
    # Si se proporciona un argumento por línea de comandos, usarlo como nombre del medicamento
    if len(sys.argv) > 1:
        medicamento = " ".join(sys.argv[1:])
    else:
        # De lo contrario, pedir al usuario
        medicamento = input("Ingrese el nombre del medicamento a buscar: ")
    
    # ✅ NUEVO: Mostrar normalización
    medicamento_normalizado = normalizar_busqueda_nadro(medicamento)
    print(f"\n=== NORMALIZACIÓN NADRO ===")
    print(f"Original: {medicamento}")
    print(f"Normalizado: {medicamento_normalizado}")
    print("=" * 40)
    
    print(f"\nBuscando información sobre: {medicamento_normalizado}")
    print("Espere un momento...\n")
    
    # Buscar información del medicamento
    info = buscar_info_medicamento(medicamento)
    
    # Verificar el estado del resultado
    estado = info.get('estado', 'desconocido')
    
    if estado == 'encontrado':
        print("\n=== INFORMACIÓN DEL PRODUCTO ===")
        print(f"Nombre: {info.get('nombre', 'No disponible')}")
        print(f"Precio: {info.get('precio', 'No disponible')}")
        print(f"Laboratorio: {info.get('laboratorio', 'No disponible')}")
        print(f"Existencia: {info.get('existencia', 'No disponible')}")
        print(f"URL: {info.get('url', 'No disponible')}")
        print("\nResultado: Producto encontrado con similitud 80%+ y sesión limpia")
    else:
        print(f"\n{info.get('mensaje', info.get('error', 'No se pudo obtener información del producto'))}")
        print(f"\nEstado: {estado}")
    
    # Guardar resultado como JSON para procesamiento externo
    try:
        output_file = f"{medicamento.replace(' ', '_')}_resultado.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(info, f, ensure_ascii=False, indent=4)
        print(f"\nResultado guardado en: {output_file}")
    except Exception as e:
        print(f"\nError al guardar resultado: {e}")
    
    # Pruebas de similitud si se ejecuta directamente
    print("\n🧪 PRUEBAS SIMILITUD 80%+:")
    casos_prueba = [
        ("paracetamol 500mg", "PARACETAMOL 500MG TABLETAS"),
        ("losartan 50mg", "LOSARTAN POTASICO 50MG"),
        ("ibuprofeno", "IBUPROFENO SUSPENSION 100ML"),
    ]
    
    for consulta, producto in casos_prueba:
        similitud = calcular_similitud_nadro_80(consulta, producto)
        valido = similitud >= 0.80
        print(f"'{consulta}' vs '{producto}': {similitud:.3f} {'✅' if valido else '❌'}")
