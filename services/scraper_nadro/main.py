#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Módulo principal para el scraper de NADRO.
Proporciona funcionalidad para buscar información de productos en el portal NADRO.
ACTUALIZADO: Con normalización específica para NADRO (nombre + cantidad separados).
REGLA NADRO: Nombre del principio activo + cantidad separada.
"""

import time
import json
import random
import traceback
import logging
import re
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

def safe_driver_quit(driver):
    """Cierra el navegador de forma segura"""
    try:
        if driver:
            driver.quit()
    except Exception as e:
        logger.error(f"Error al cerrar el navegador: {e}")
        # Intento alternativo para cerrar procesos
        try:
            import os
            os.system("taskkill /f /im chromedriver.exe")
            os.system("taskkill /f /im chrome.exe")
        except:
            pass

def inicializar_navegador(headless=True):
    """
    Inicializa el navegador Chrome con webdriver-manager para
    compatible con entorno Google Cloud.

    Args:
        headless (bool): Si es True, el navegador se ejecuta en modo headless

    Returns:
        WebDriver: Instancia del navegador
    """
    if UNDETECTED_AVAILABLE:
        try:
            logger.info("Iniciando navegador no detectable...")
            
            # Configuración avanzada de undetected_chromedriver
            options = uc.ChromeOptions()
            options.add_argument("--disable-blink-features=AutomationControlled")
            options.add_argument("--disable-extensions")
            options.add_argument("--disable-popup-blocking")
            options.add_argument("--disable-notifications")
            
            # Opciones para entorno headless compatible con Cloud
            if headless:
                options.add_argument("--headless=new")
                options.add_argument("--no-sandbox")
                options.add_argument("--disable-dev-shm-usage")
            
            # Tamaño de ventana aleatorio para parecer más humano
            width = random.randint(1100, 1300)
            height = random.randint(700, 900)
            options.add_argument(f"--window-size={width},{height}")
            
            # User Agent aleatorio
            user_agents = [
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36 Edg/119.0.0.0",
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.5 Safari/605.1.15"
            ]
            options.add_argument(f"--user-agent={random.choice(user_agents)}")
            
            # Inicializar navegador con opciones
            driver = uc.Chrome(options=options)
            logger.info("Navegador no detectable inicializado correctamente")
            return driver
            
        except Exception as e:
            logger.error(f"Error al inicializar navegador no detectable: {e}")
            logger.info("Intentando con navegador estándar...")
            # Si falla, usaremos selenium estándar como respaldo
    
    # Selenium estándar (respaldo o si undetected no está disponible)
    try:
        options = webdriver.ChromeOptions() if not UNDETECTED_AVAILABLE else Options()
        
        if headless:
            options.add_argument("--headless=new")
        
        # Configuración adicional para entorno sin interfaz gráfica
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--disable-notifications")
        
        # Configuración para evitar detección de automatización
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)
        
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        
        # Ejecutar JavaScript para eludir detección
        driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
            "source": """
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
            """
        })
        
        logger.info("Navegador estándar inicializado correctamente")
        return driver
        
    except Exception as e:
        logger.error(f"Error al inicializar navegador estándar: {e}")
        return None

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
            logger.info(f"✅ BÚSQUEDA COMPLETADA: {len(resultados)} productos procesados")
            return {"success": True, "productos": resultados}
        else:
            logger.warning(f"⚠️ No se pudieron procesar productos de la lista")
            return {"warning": "No se pudo extraer información de productos", "productos": []}

    except Exception as e:
        logger.error(f"Error durante la búsqueda de producto: {e}")
        traceback.print_exc()
        return {"error": str(e), "productos": []}

def login_and_search(producto):
    """
    Función principal: login y búsqueda de producto
    
    Args:
        producto: nombre del producto a buscar (YA NORMALIZADO)
        
    Returns:
        dict: Resultado con información de productos o error
    """
    driver = None
    try:
        # Inicializar navegador
        driver = inicializar_navegador(headless=True)
        if not driver:
            return {"error": "No se pudo inicializar el navegador", "productos": []}
        
        try:
            # Navegar a la página principal
            logger.info(f"Navegando a {MAIN_URL}...")
            driver.get(MAIN_URL)
            random_delay(3, 5)
            
            # Buscar el enlace o botón de login
            logger.info("Buscando enlace de login...")
            login_link_found = False
            
            # Intentar diferentes elementos que podrían ser enlaces de login
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
                            logger.info(f"Enlace de login encontrado. Haciendo clic...")
                            element.click()
                            login_link_found = True
                            random_delay(3, 5)  # Esperar a que la página de login cargue
                            break
                    if login_link_found:
                        break
                except:
                    continue
            
            # Si no encontramos enlaces, intentar con URL directa de login
            if not login_link_found:
                logger.info("No se encontró enlace de login. Intentando con URL de login directa...")
                driver.get("https://i22.nadro.mx/login")
                random_delay(3, 5)
            
            # Esperar a que cargue el formulario de login
            logger.info("Esperando formulario de login...")
            random_delay(5, 8)
            
            # Guardar captura de la página de login para análisis
            debug_dir = Path("debug_screenshots")
            debug_dir.mkdir(exist_ok=True)
            screenshot_path = str(debug_dir.joinpath("pagina_login.png"))
            driver.save_screenshot(screenshot_path)
            
            # Buscar campo de usuario con espera explícita
            logger.info("Buscando campo de usuario...")
            try:
                username_field = WebDriverWait(driver, 15).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, "input[type='text'], input[type='email'], #username, input[name='username']"))
                )
                
                # Escribir usuario
                logger.info(f"Ingresando usuario: {USERNAME}")
                username_field.clear()
                random_delay(0.5, 1.5)
                
                # Escritura humana con pausas variables
                for c in USERNAME:
                    username_field.send_keys(c)
                    random_delay(0.1, 0.3)
                
                random_delay(0.5, 1.5)
                
                # Buscar campo de contraseña
                logger.info("Buscando campo de contraseña...")
                password_field = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, "input[type='password'], #password, input[name='password']"))
                )
                
                # Escribir contraseña
                logger.info("Ingresando contraseña...")
                password_field.clear()
                random_delay(0.5, 1.5)
                
                for c in PASSWORD:
                    password_field.send_keys(c)
                    random_delay(0.1, 0.3)
                
                random_delay(1, 2)
                
                # Buscar botón de login
                logger.info("Buscando botón de login...")
                login_button = None
                
                # Intentar encontrar por diferentes selectores
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
                
                # Clic en botón o Enter en contraseña
                if login_button:
                    logger.info("Haciendo clic en botón de login...")
                    login_button.click()
                else:
                    logger.info("No se encontró botón. Enviando con Enter...")
                    password_field.send_keys(Keys.RETURN)
                
                # Esperar procesamiento de login
                logger.info("Procesando login...")
                random_delay(8, 12)
                
                # Tomar captura después del login
                screenshot_path = str(Path("debug_screenshots").joinpath("despues_login.png"))
                driver.save_screenshot(screenshot_path)
                
                # Verificar login exitoso - más métodos de verificación
                login_exitoso = False
                
                # Método 1: Verificar URL
                if "login" not in driver.current_url.lower() or "account" in driver.current_url.lower():
                    login_exitoso = True
                
                # Método 2: Buscar elementos que solo aparecen después del login
                if not login_exitoso:
                    try:
                        # Elementos que suelen aparecer después de login exitoso
                        post_login_elements = [
                            "a[href*='logout']",
                            "span:contains('Cerrar sesión')",
                            "div.vtex-login-2-x-profile",
                            "div.vtex-login-2-x-container--logged"
                        ]
                        
                        for selector in post_login_elements:
                            elements = driver.find_elements(By.CSS_SELECTOR, selector)
                            if elements and any(e.is_displayed() for e in elements):
                                login_exitoso = True
                                break
                    except:
                        pass
                
                # Si detectamos login exitoso
                if login_exitoso:
                    logger.info("Login exitoso. Procediendo con la búsqueda...")
                    
                    # Realizar búsqueda del producto NORMALIZADO
                    resultado = buscar_producto(driver, producto)
                    return resultado
                else:
                    logger.warning("Login fallido. URL actual:" + driver.current_url)
                    
                    # Guardar HTML para análisis
                    debug_logs_dir = Path("debug_logs")
                    debug_logs_dir.mkdir(exist_ok=True)
                    html_path = str(debug_logs_dir.joinpath("login_fallido.html"))
                    with open(html_path, "w", encoding="utf-8") as f:
                        f.write(driver.page_source)
                    
                    # Intentar verificar mensaje de error
                    try:
                        error_selectors = [
                            ".error-message",
                            ".alert-danger",
                            "#errorMessage",
                            "div[role='alert']"
                        ]
                        
                        for selector in error_selectors:
                            elements = driver.find_elements(By.CSS_SELECTOR, selector)
                            for el in elements:
                                if el.is_displayed() and el.text.strip():
                                    error_msg = el.text.strip()
                                    logger.warning(f"Mensaje de error detectado: {error_msg}")
                                    return {"error": f"Login fallido: {error_msg}", "productos": []}
                    except:
                        pass
                    
                    return {"error": "Login fallido. Posible cambio en la página de login o credenciales inválidas.", "productos": []}
                
            except Exception as e:
                logger.error(f"Error durante el proceso de login: {e}")
                screenshot_path = str(Path("debug_screenshots").joinpath("error_login.png"))
                driver.save_screenshot(screenshot_path)
                html_path = str(Path("debug_logs").joinpath("error_login.html"))
                with open(html_path, "w", encoding="utf-8") as f:
                    f.write(driver.page_source)
                return {"error": f"Error de login: {str(e)}", "productos": []}
            
        finally:
            # Cerrar navegador de forma segura
            logger.info("Cerrando navegador...")
            safe_driver_quit(driver)
    
    except Exception as e:
        logger.error(f"Error general: {e}")
        traceback.print_exc()
        if driver:
            safe_driver_quit(driver)
        return {"error": str(e), "productos": []}

def buscar_info_medicamento(nombre_medicamento, headless=True):
    """
    Función principal que busca información de un medicamento en NADRO.
    ACTUALIZADO: Con normalización específica para NADRO.
    
    Args:
        nombre_medicamento (str): Nombre del medicamento a buscar
        headless (bool): Si es True, el navegador se ejecuta en modo headless
        
    Returns:
        dict: Diccionario con la información del medicamento en formato compatible
    """
    try:
        logger.info(f"Iniciando búsqueda de {nombre_medicamento} en NADRO")
        
        # ✅ NUEVO: Normalizar búsqueda para NADRO
        nombre_normalizado = normalizar_busqueda_nadro(nombre_medicamento)
        
        # Crear directorios para debug si no existen
        Path("debug_screenshots").mkdir(exist_ok=True)
        Path("debug_logs").mkdir(exist_ok=True)
        
        # Llamar a la función principal de búsqueda con nombre normalizado
        resultado = login_and_search(nombre_normalizado)
        
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
            
            logger.info(f"✅ Producto encontrado en NADRO: {info_producto['nombre']} - Precio: {info_producto['precio']} - Existencia: {info_producto['existencia']}")
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
        logger.error(f"Error general en buscar_info_medicamento: {e}")
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
        print("\nResultado: Producto encontrado")
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
