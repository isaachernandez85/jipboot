"""
Módulo de scraping específico para la farmacia Sufarmed.
ACTUALIZADO: Con normalización de búsqueda específica para Sufarmed.
REGLA SUFARMED: Solo nombre del principio activo (sin formas farmacéuticas ni dosis).
"""
import logging
import time
import re
import os
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException, 
    NoSuchElementException,
    ElementClickInterceptedException,
    WebDriverException
)
from config.settings import HEADLESS_BROWSER

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def normalizar_busqueda_sufarmed(producto_nombre):
    """
    Normaliza la búsqueda para SUFARMED: solo nombre del principio activo.
    Ejemplo: "diclofenaco inyectable 75 mg" → "diclofenaco"
    
    Args:
        producto_nombre (str): Nombre completo del producto
        
    Returns:
        str: Solo el nombre del principio activo
    """
    if not producto_nombre:
        return producto_nombre
    
    # Convertir a minúsculas para procesamiento
    texto = producto_nombre.lower().strip()
    
    # Formas farmacéuticas y palabras a eliminar
    palabras_eliminar = [
        # Formas farmacéuticas
        'inyectable', 'tabletas', 'tablets', 'cápsulas', 'capsulas', 
        'jarabe', 'solución', 'solucion', 'crema', 'gel', 'ungüento',
        'gotas', 'ampolletas', 'ampollas', 'suspensión', 'suspension',
        'comprimidos', 'pastillas', 'tabs', 'cap', 'sol', 'iny',
        'ampolla', 'vial', 'frasco', 'sobre', 'tubo',
        # Concentraciones y unidades
        'mg', 'g', 'ml', 'mcg', 'ui', 'iu', '%', 'cc', 'mgs',
        # Números (cualquier número será eliminado)
    ]
    
    # Dividir en palabras
    palabras = texto.split()
    palabras_filtradas = []
    
    for palabra in palabras:
        # Eliminar números
        if re.match(r'^\d+(?:\.\d+)?$', palabra):
            continue
        # Eliminar números con unidades pegadas (ej: "75mg", "10ml")
        if re.match(r'^\d+(?:\.\d+)?(mg|g|ml|mcg|ui|iu|%|cc)$', palabra):
            continue
        # Eliminar palabras de la lista
        if palabra in palabras_eliminar:
            continue
        # Mantener solo palabras del nombre del principio activo
        palabras_filtradas.append(palabra)
    
    # Tomar solo la primera palabra significativa (el principio activo principal)
    if palabras_filtradas:
        resultado = palabras_filtradas[0]
    else:
        # Si no queda nada, usar la primera palabra original
        resultado = producto_nombre.split()[0] if producto_nombre.split() else producto_nombre
    
    logger.info(f"[SUFARMED] Normalización: '{producto_nombre}' → '{resultado}'")
    return resultado

class ScrapingService:
    """
    Clase que proporciona métodos para buscar información de productos farmacéuticos
    mediante scraping en Sufarmed.
    """
    
    def __init__(self, headless: bool = HEADLESS_BROWSER,
                username: str = "laubec83@gmail.com", 
                password: str = "Sr3ChK8pBoSEScZ",
                login_url: str = "https://sufarmed.com/sufarmed/iniciar-sesion"):
        """
        Inicializa el servicio de scraping
        
        Args:
            headless (bool): Si es True, el navegador se ejecuta en modo headless
            username (str): Nombre de usuario para login
            password (str): Contraseña para login
            login_url (str): URL de la página de login
        """
        self.headless = headless
        self.username = username
        self.password = password
        self.login_url = login_url
        self.timeout = 15
        logger.info("ScrapingService para Sufarmed inicializado")
    
    def buscar_producto(self, nombre_producto: str) -> dict:
        """
        Busca un producto en Sufarmed y extrae su información.
        Método principal para compatibilidad con el servicio integrado.
        ACTUALIZADO: Con normalización específica para Sufarmed.
        
        Args:
            nombre_producto (str): Nombre del producto a buscar
            
        Returns:
            dict: Información del producto o None si no se encuentra
        """
        logger.info(f"Iniciando búsqueda en Sufarmed para: '{nombre_producto}'")
        
        # ✅ NUEVO: Normalizar búsqueda para Sufarmed
        nombre_normalizado = normalizar_busqueda_sufarmed(nombre_producto)
        
        return buscar_producto_sufarmed(nombre_normalizado)

def find_one(driver, wait, candidates):
    """
    Prueba varios selectores y devuelve el primer elemento encontrado.
    candidates: [(By, selector), ...]
    """
    for by, sel in candidates:
        try:
            return wait.until(EC.presence_of_element_located((by, sel)))
        except TimeoutException:
            continue
    raise NoSuchElementException(f"No se encontró ninguno de {candidates}")

def inicializar_navegador(headless: bool = HEADLESS_BROWSER):
    """
    Inicializa el navegador Chrome de forma compatible con entornos Docker/headless.
    Usa el binario de Chrome preinstalado en lugar de depender de webdriver-manager.
    """
    # Rutas predefinidas para entornos Docker
    chrome_binary_path = "/usr/bin/google-chrome"
    
    options = webdriver.ChromeOptions()
    
    # Configuración para entorno headless
    if headless:
        options.add_argument("--headless=new")  # Versión moderna del flag headless
    
    # Opciones críticas para entorno Docker/containerizado
    options.add_argument("--no-sandbox")  # Requerido para ejecutar Chrome en contenedor
    options.add_argument("--disable-dev-shm-usage")  # Evita problemas de memoria compartida
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-notifications")
    options.add_argument("--disable-popup-blocking")
    
    # Especificar la ruta al binario Chrome
    options.binary_location = chrome_binary_path
    
    try:
        # Verificar que el binario de Chrome existe
        if not os.path.exists(chrome_binary_path):
            logger.error(f"Binario de Chrome no encontrado en: {chrome_binary_path}")
            return None
        
        # En Selenium 4, no es necesario especificar el chromedriver, se descarga automáticamente
        logger.info("Inicializando Chrome en modo compatible con Docker")
        driver = webdriver.Chrome(options=options)
        
        # Verificar que el navegador se inicializó correctamente
        user_agent = driver.execute_script("return navigator.userAgent")
        logger.info(f"Navegador inicializado correctamente con User-Agent: {user_agent}")
        
        # Establecer timeouts razonables
        driver.set_page_load_timeout(30)
        driver.implicitly_wait(10)
        
        return driver
    except WebDriverException as e:
        logger.error(f"Error específico de WebDriver al inicializar Chrome: {e}")
        return None
    except Exception as e:
        logger.error(f"Error general al inicializar el navegador: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return None

def login(driver, username, password, login_url, timeout):
    """
    Realiza el inicio de sesión en Sufarmed
    
    Args:
        driver (webdriver.Chrome): Instancia del navegador
        username (str): Nombre de usuario
        password (str): Contraseña
        login_url (str): URL de la página de login
        timeout (int): Tiempo máximo de espera
        
    Returns:
        bool: True si el login fue exitoso, False en caso contrario
    """
    try:
        wait = WebDriverWait(driver, timeout)
        
        # 1) Abre login
        logger.info(f"Navegando a la página de login: {login_url}")
        driver.get(login_url)
        time.sleep(2)

        # 2) Cierra banner cookies/GDPR si existe
        try:
            btn = driver.find_element(
                By.CSS_SELECTOR,
                ".js-cookie-accept, .gdpr-accept, button[aria-label*='Aceptar']"
            )
            btn.click()
            logger.info("Banner de cookies cerrado")
            time.sleep(1)
        except NoSuchElementException:
            logger.info("No se encontró banner de cookies")

        # 3) Inputs de email y contraseña
        logger.info("Buscando campos de login")
        email = find_one(driver, wait, [
            (By.ID,           "email"),
            (By.NAME,         "email"),
            (By.CSS_SELECTOR, "input[type='email']"),
        ])
        pwd = find_one(driver, wait, [
            (By.ID,           "passwd"),
            (By.NAME,         "password"),
            (By.CSS_SELECTOR, "input[type='password']"),
        ])

        # 4) Ingresar credenciales
        logger.info(f"Ingresando credenciales para usuario: {username}")
        email.clear()
        email.send_keys(username)
        pwd.clear()
        pwd.send_keys(password)

        # 5) **Botón EXACTO de "Iniciar sesión" dentro del form**
        login_button = find_one(driver, wait, [
            # Selector puro dentro del form#login-form
            (By.CSS_SELECTOR, "form#login-form button[type='submit']"),
            # alternativo, por texto exacto
            (By.XPATH, "//form[@id='login-form']//button[contains(normalize-space(),'Iniciar sesión')]"),
        ])

        # Asegura que esté a la vista
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", login_button)
        time.sleep(0.3)

        # Click (con fallback JS)
        try:
            login_button.click()
            logger.info("Botón de login clickeado")
        except ElementClickInterceptedException:
            driver.execute_script("arguments[0].click();", login_button)
            logger.info("Botón de login clickeado mediante JavaScript")

        # 6) Espera a que realmente entres a "Mi cuenta"
        try:
            wait.until(EC.url_contains("/mi-cuenta"))
            logger.info("✅ Redirigido a /mi-cuenta")
        except TimeoutException:
            logger.warning("No se detectó redirección a /mi-cuenta")

        # 7) Verifica el menú de usuario
        time.sleep(2)
        if driver.find_elements(By.CSS_SELECTOR, "a.account"):
            logger.info("✅ Login validado – elemento `.account` presente.")
            return True
        else:
            logger.error("❌ Login parece fallido.")
            # Capturar evidencia para debugging
            try:
                driver.save_screenshot("after_login.png")
            except Exception as e:
                logger.warning(f"No se pudo guardar captura de pantalla: {e}")
            return False

    except Exception as e:
        logger.error(f"Error durante el login: {e}")
        return False

def es_pagina_producto(driver):
    """
    Verifica si la página actual es una página de producto.
    
    Args:
        driver (webdriver.Chrome): Instancia del navegador
        
    Returns:
        bool: True si es una página de producto, False en caso contrario
    """
    try:
        # Capturar la URL actual para depuración
        current_url = driver.current_url
        logger.info(f"Verificando si es página de producto: {current_url}")
        
        # Verificar múltiples elementos que indican que estamos en una página de producto
        indicadores = [
            # Verificación original
            bool(driver.find_elements(By.CSS_SELECTOR, "h1[itemprop='name']")),
            
            # Otras verificaciones posibles
            bool(driver.find_elements(By.CSS_SELECTOR, ".product_header_container, .product-detail-name, .page-product-box")),
            "product-information" in driver.page_source,
            "detalles-del-producto" in driver.page_source,
            "detalles del producto" in driver.page_source.lower(),
            # Verificar si el body tiene la clase 'product-available-for-order' o 'product-out-of-stock'
            "product-available-for-order" in driver.find_element(By.TAG_NAME, "body").get_attribute("class"),
            "product-out-of-stock" in driver.find_element(By.TAG_NAME, "body").get_attribute("class")
        ]
        
        # Si cualquiera de los indicadores es True, consideramos que es una página de producto
        es_producto = any(indicadores)
        logger.info(f"¿Es página de producto? {es_producto}")
        
        return es_producto
    
    except Exception as e:
        logger.error(f"Error al verificar si es página de producto: {e}")
        return False

def extraer_info_producto(driver):
    """
    Extrae la información relevante del producto desde la página actual.
    Con enfoque simplificado pero robusto para detección de disponibilidad.
    
    Args:
        driver (webdriver.Chrome): Instancia del navegador
        
    Returns:
        dict: Diccionario con la información extraída
    """
    try:
        # Inicializar el diccionario de resultado
        info_producto = {
            "nombre": None,
            "laboratorio": None,
            "codigo_barras": None,
            "registro_sanitario": None,
            "url": driver.current_url,
            "imagen": None,
            "precio": None,
            "stock": None,
            "disponible": False,  # Por defecto, asumimos que NO está disponible hasta confirmar
            "existencia": "0"  # Añadido para compatibilidad con el servicio integrado
        }
        
        logger.info(f"Extrayendo información del producto en URL: {info_producto['url']}")
        
        # Dar tiempo para que la página cargue completamente
        time.sleep(3)
        
        # =============== DETECCIÓN DE DISPONIBILIDAD MEJORADA ===============
        try:
            # PASO 1: Buscar elementos visuales explícitos (marcador verde "Disponible")
            elementos_disponible = driver.find_elements(By.CSS_SELECTOR, ".disponible, span.disponible, div.disponible, .label-success, .alert-success, .stock-disponible")
            for elem in elementos_disponible:
                if elem.is_displayed():
                    texto = elem.text.strip()
                    logger.info(f"Elemento 'disponible' encontrado: {texto}")
                    info_producto["stock"] = texto if texto else "Disponible"
                    info_producto["disponible"] = True
                    # Buscar si hay un número específico
                    match = re.search(r'(\d+)', texto)
                    if match:
                        info_producto["existencia"] = match.group(1)
                    else:
                        info_producto["existencia"] = "Si" # Valor por defecto para productos disponibles sin cantidad específica
                    break
            
            # PASO 2: Buscar "En existencia" con número de artículos
            if not info_producto["stock"]:
                elementos_existencia = driver.find_elements(By.XPATH, "//*[contains(text(), 'En existencia') or contains(text(), 'existencia') or contains(text(), 'En stock')]")
                for elem in elementos_existencia:
                    if elem.is_displayed():
                        texto = elem.text.strip()
                        logger.info(f"Elemento 'En existencia' encontrado: {texto}")
                        # Extraer número si existe
                        match = re.search(r'(\d+)', texto)
                        if match:
                            cantidad = int(match.group(1))
                            if cantidad > 0:
                                info_producto["stock"] = texto
                                info_producto["disponible"] = True
                                info_producto["existencia"] = match.group(1)
                                break
                        else:
                            # Si no hay número pero indica existencia
                            info_producto["stock"] = texto
                            info_producto["disponible"] = True
                            info_producto["existencia"] = "Si" # Valor por defecto si no hay cantidad
                            break
            
            # PASO 3: Buscar elementos visuales de "Agotado"
            if not info_producto["stock"]:
                elementos_agotado = driver.find_elements(By.CSS_SELECTOR, ".agotado, .producto-agotado, .label-danger, .alert-danger, .out-of-stock")
                if not elementos_agotado:
                    elementos_agotado = driver.find_elements(By.XPATH, "//*[contains(text(), 'Agotado') or contains(text(), 'agotado') or contains(text(), 'AGOTADO') or contains(text(), 'Producto Agotado')]")
                    
                for elem in elementos_agotado:
                    if elem.is_displayed():
                        texto = elem.text.strip()
                        logger.info(f"Elemento 'agotado' encontrado: {texto}")
                        info_producto["stock"] = texto if texto else "Producto Agotado"
                        info_producto["disponible"] = False
                        info_producto["existencia"] = "0"
                        break
            
            # PASO 4: Buscar selectores comunes de stock y disponibilidad
            if not info_producto["stock"]:
                selectores_stock = [
                    "#availability_value", 
                    ".availability-value",
                    "#product-availability",
                    ".stock-label",
                    "[itemprop='availability']",
                    ".product-stock",
                    ".availability"
                ]
                
                for selector in selectores_stock:
                    try:
                        elementos = driver.find_elements(By.CSS_SELECTOR, selector)
                        for elem in elementos:
                            if elem.is_displayed():
                                texto = elem.text.strip()
                                if texto:
                                    logger.info(f"Texto de disponibilidad encontrado con selector '{selector}': {texto}")
                                    info_producto["stock"] = texto
                                    
                                    # Determinar disponibilidad basada en texto
                                    texto_lower = texto.lower()
                                    if "disponible" in texto_lower and not "no disponible" in texto_lower:
                                        info_producto["disponible"] = True
                                        info_producto["existencia"] = "Si"
                                        # Intentar extraer un número
                                        match = re.search(r'(\d+)', texto)
                                        if match:
                                            info_producto["existencia"] = match.group(1)
                                    elif any(term in texto_lower for term in ["agotado", "sin existencias", "no disponible"]):
                                        info_producto["disponible"] = False
                                        info_producto["existencia"] = "0"
                                    break
                        
                        if info_producto["stock"]:
                            break
                    except Exception as e:
                        logger.warning(f"Error al buscar stock con selector '{selector}': {e}")
            
            # PASO 5: Buscar "En stock" o "Disponible" en texto general si aún no hay resultado
            if not info_producto["stock"]:
                page_text = driver.find_element(By.TAG_NAME, "body").text.lower()
                
                # Buscar indicadores de disponibilidad
                if "disponible" in page_text and not "no disponible" in page_text:
                    info_producto["stock"] = "Disponible"
                    info_producto["disponible"] = True
                    info_producto["existencia"] = "Si"
                    logger.info("Producto marcado como disponible por texto general")
                # Buscar indicadores de agotado
                elif any(term in page_text for term in ["agotado", "sin stock", "sin existencias"]):
                    info_producto["stock"] = "Producto Agotado"
                    info_producto["disponible"] = False
                    info_producto["existencia"] = "0"
                    logger.info("Producto marcado como agotado por texto general")
                
            # PASO 6: Verificar si hay botón de "Añadir al carrito" no deshabilitado (último recurso)
            if not info_producto["stock"]:
                botones_carrito = driver.find_elements(By.CSS_SELECTOR, 
                    "#add_to_cart:not([disabled]), .add-to-cart:not([disabled]), button[name='Submit']:not([disabled])")
                
                if botones_carrito:
                    for boton in botones_carrito:
                        if boton.is_displayed() and not "disabled" in boton.get_attribute("class"):
                            logger.info("Botón de añadir al carrito activo encontrado")
                            info_producto["stock"] = "Disponible"
                            info_producto["disponible"] = True
                            info_producto["existencia"] = "Si"
                            break
                else:
                    # Si no hay botón de añadir o está deshabilitado, puede indicar que no hay stock
                    botones_deshabilitados = driver.find_elements(By.CSS_SELECTOR, 
                        "#add_to_cart[disabled], .add-to-cart[disabled], button[name='Submit'][disabled], .disabled")
                    
                    if botones_deshabilitados:
                        for boton in botones_deshabilitados:
                            if boton.is_displayed():
                                logger.info("Botón de añadir al carrito deshabilitado encontrado")
                                info_producto["stock"] = "Producto Agotado"
                                info_producto["disponible"] = False
                                info_producto["existencia"] = "0"
                                break
                
            # Si después de todo no se ha encontrado nada, marcamos como desconocido
            if not info_producto["stock"]:
                info_producto["stock"] = "Estado desconocido"
                info_producto["disponible"] = False
                info_producto["existencia"] = "0"
                logger.warning("No se pudo determinar el estado de stock")
            
            logger.info(f"Estado final de stock: {info_producto['stock']} - Disponible: {info_producto['disponible']} - Existencia: {info_producto['existencia']}")
            
        except Exception as e:
            logger.error(f"Error al extraer información de stock: {e}")
            info_producto["stock"] = "Error al determinar stock"
            info_producto["disponible"] = False
            info_producto["existencia"] = "0"
        
        # Extraer el nombre del producto
        try:
            nombre_elem = driver.find_element(By.CSS_SELECTOR, "h1[itemprop='name']")
            info_producto["nombre"] = nombre_elem.text.strip()
            logger.info(f"Nombre del producto extraído: {info_producto['nombre']}")
        except NoSuchElementException:
            try:
                # Intentar con otro selector alternativo
                nombre_elem = driver.find_element(By.CSS_SELECTOR, ".product_header_container h1, .page-heading")
                info_producto["nombre"] = nombre_elem.text.strip()
                logger.info(f"Nombre del producto extraído (selector alternativo): {info_producto['nombre']}")
            except NoSuchElementException:
                logger.warning("No se pudo encontrar el nombre del producto")
        
        # Extraer el precio del producto
        try:
            # Intentar diferentes selectores para el precio
            precio_selectores = [
                ".current-price span", 
                ".product-price", 
                ".our_price_display", 
                "#our_price_display",
                ".price",
                "[itemprop='price']",
                ".product-price-and-shipping span.price",
                ".product-price .current-price"
            ]
            
            for selector in precio_selectores:
                try:
                    precio_elem = driver.find_element(By.CSS_SELECTOR, selector)
                    precio_texto = precio_elem.text.strip()
                    # Asegurarse de que realmente es un precio (contiene cifras y posiblemente símbolos de dinero)
                    if any(char.isdigit() for char in precio_texto):
                        info_producto["precio"] = precio_texto
                        logger.info(f"Precio extraído: {info_producto['precio']}")
                        break
                except NoSuchElementException:
                    continue
                    
            if not info_producto["precio"]:
                # Intento adicional con XPath más específicos
                xpath_precios = [
                    "//div[contains(@class, 'product-price')]/span",
                    "//div[contains(@class, 'price')]//span[contains(@class, 'price')]",
                    "//span[@itemprop='price']",
                    "//div[contains(@class, 'product-information')]//span[contains(@class, 'price')]"
                ]
                
                for xpath in xpath_precios:
                    try:
                        precio_elem = driver.find_element(By.XPATH, xpath)
                        precio_texto = precio_elem.text.strip()
                        if any(char.isdigit() for char in precio_texto):
                            info_producto["precio"] = precio_texto
                            logger.info(f"Precio extraído (XPath): {info_producto['precio']}")
                            break
                    except NoSuchElementException:
                        continue
                
                # Buscar en metadatos si no se encuentra en elementos visibles
                if not info_producto["precio"]:
                    try:
                        meta_precio = driver.find_element(By.CSS_SELECTOR, "meta[property='product:price:amount']")
                        if meta_precio:
                            precio_valor = meta_precio.get_attribute("content")
                            if precio_valor and any(char.isdigit() for char in precio_valor):
                                info_producto["precio"] = f"$ {precio_valor}"
                                logger.info(f"Precio extraído de metadatos: {info_producto['precio']}")
                    except:
                        pass
                
                if not info_producto["precio"]:
                    logger.warning("No se pudo encontrar el precio del producto")
        except Exception as e:
            logger.warning(f"Error al extraer precio: {e}")
        
        # Extraer la imagen del producto
        try:
            imagen_elem = driver.find_element(By.CSS_SELECTOR, "#bigpic")
            info_producto["imagen"] = imagen_elem.get_attribute("src")
            logger.info(f"URL de imagen extraída: {info_producto['imagen']}")
        except NoSuchElementException:
            try:
                # Intentar con otros selectores alternativos para la imagen
                selectores_imagen = [
                    ".product-detail-picture img", 
                    ".product_img_link img", 
                    ".product-image img",
                    ".col-product-image img",
                    "#product-modal img",
                    ".col-md-5 img",
                    ".col-product-image img"
                ]
                
                for selector in selectores_imagen:
                    try:
                        imagen_elem = driver.find_element(By.CSS_SELECTOR, selector)
                        info_producto["imagen"] = imagen_elem.get_attribute("src")
                        logger.info(f"URL de imagen extraída ({selector}): {info_producto['imagen']}")
                        break
                    except NoSuchElementException:
                        continue
                
                if not info_producto["imagen"]:
                    logger.warning("No se pudo encontrar la imagen del producto con ningún selector")
            except Exception as e:
                logger.warning(f"Error al buscar imagen alternativa: {e}")
        
       # Cambiar a la pestaña de detalles del producto si existe
        try:
            # Encontrar y hacer clic en la pestaña de detalles
            pestanas = driver.find_elements(By.CSS_SELECTOR, "a[href*='#detalles-del-producto'], a[href*='#product-details'], a[data-toggle='tab']") # Usar * para flexibilidad
            detalles_clickeado = False
            for pestana in pestanas:
                try:
                    texto_pestana = pestana.text.lower()
                    if "detalles" in texto_pestana or "características" in texto_pestana or "descripción" in texto_pestana:
                        logger.info(f"Haciendo clic en pestaña: {pestana.text}")
                        driver.execute_script("arguments[0].click();", pestana)
                        time.sleep(1)  # Pequeña pausa para que cargue el contenido
                        detalles_clickeado = True
                        break
                except Exception:
                    pass
            
            if not detalles_clickeado:
                logger.info("No se encontró pestaña de detalles o no se pudo hacer clic en ella")
        except Exception as e:
            logger.warning(f"Error al intentar cambiar a la pestaña de detalles: {e}")
        
        # Extraer información basada en estructura dt/dd
        try:
            logger.info("Buscando información en estructura dt/dd...")
            
            # Buscar todos los dt (términos) y sus dd (definiciones) asociados
            dt_elements = driver.find_elements(By.CSS_SELECTOR, "dt.name, dt")
            
            for dt in dt_elements:
                try:
                    # Obtener el texto del término
                    term_text = dt.text.strip().lower()
                    logger.info(f"Término encontrado: {term_text}")
                    
                    # Buscar el dd asociado (puede ser el siguiente elemento hermano)
                    dd = None
                    
                    # Método 1: Buscar el siguiente elemento hermano directamente
                    try:
                        dd = dt.find_element(By.XPATH, "./following-sibling::dd[1]")
                    except Exception:
                        # Método 2: Buscar por JavaScript
                        try:
                            dd_script = """
                            return arguments[0].nextElementSibling;
                            """
                            dd = driver.execute_script(dd_script, dt)
                        except Exception:
                            pass
                    
                    if dd:
                        value_text = dd.text.strip()
                        logger.info(f"Valor asociado: {value_text}")
                        
                        # Mapear los términos a nuestros campos
                        if "laboratorio" in term_text:
                            info_producto["laboratorio"] = value_text
                            logger.info(f"Laboratorio extraído: {value_text}")
                        elif ("código" in term_text and "barras" in term_text) or "código de barras" in term_text:
                            info_producto["codigo_barras"] = value_text
                            logger.info(f"Código de barras extraído: {value_text}")
                        elif "registro" in term_text and "sanitario" in term_text:
                            info_producto["registro_sanitario"] = value_text
                            logger.info(f"Registro sanitario extraído: {value_text}")
                except Exception as e:
                    logger.warning(f"Error al procesar término dt: {e}")
        except Exception as e:
            logger.warning(f"Error al procesar estructura dt/dd: {e}")

        # Método 2: Buscar en tablas específicas
        if not (info_producto["laboratorio"] and info_producto["codigo_barras"] and info_producto["registro_sanitario"]):
            try:
                logger.info("Buscando en tablas...")
                # Buscar filas de tabla con información
                filas = driver.find_elements(By.CSS_SELECTOR, "table tr, .table-data-sheet tr, .data-sheet tr")
                
                for fila in filas:
                    try:
                        # Obtener celdas
                        celdas = fila.find_elements(By.TAG_NAME, "td")
                        if len(celdas) >= 2:
                            clave = celdas[0].text.strip().lower()
                            valor = celdas[1].text.strip()
                            
                            # Mapear claves a nuestros campos
                            if "laboratorio" in clave and not info_producto["laboratorio"]:
                                info_producto["laboratorio"] = valor
                                logger.info(f"Laboratorio extraído de tabla: {valor}")
                            elif ("codigo" in clave and "barras" in clave) and not info_producto["codigo_barras"]:
                                info_producto["codigo_barras"] = valor
                                logger.info(f"Código de barras extraído de tabla: {valor}")
                            elif "registro" in clave and "sanitario" in clave and not info_producto["registro_sanitario"]:
                                info_producto["registro_sanitario"] = valor
                                logger.info(f"Registro sanitario extraído de tabla: {valor}")
                    except Exception as e:
                        logger.warning(f"Error al procesar fila de tabla: {e}")
            except Exception as e:
                logger.warning(f"Error al buscar en tablas: {e}")
        
        # Método 3: Buscar específicamente por XPath con el texto exacto
        if not (info_producto["laboratorio"] and info_producto["codigo_barras"] and info_producto["registro_sanitario"]):
            try:
                logger.info("Buscando con XPath específicos...")
                # Xpath para laboratorio
                if not info_producto["laboratorio"]:
                    try:
                        lab_elements = driver.find_elements(By.XPATH, "//dt[contains(text(), 'Laboratorio')]/following-sibling::dd[1] | //td[contains(text(), 'Laboratorio')]/following-sibling::td[1] | //th[contains(text(), 'Laboratorio')]/following-sibling::td[1]")
                        if lab_elements:
                            info_producto["laboratorio"] = lab_elements[0].text.strip()
                            logger.info(f"Laboratorio extraído por XPath: {info_producto['laboratorio']}")
                    except Exception:
                        pass
                # Xpath para código de barras
                if not info_producto["codigo_barras"]:
                    try:
                        barcode_elements = driver.find_elements(By.XPATH, "//dt[contains(text(), 'Código de barras')]/following-sibling::dd[1] | //td[contains(text(), 'Código de barras')]/following-sibling::td[1] | //th[contains(text(), 'Código de barras')]/following-sibling::td[1]")
                        if barcode_elements:
                            info_producto["codigo_barras"] = barcode_elements[0].text.strip()
                            logger.info(f"Código de barras extraído por XPath: {info_producto['codigo_barras']}")
                    except Exception:
                        pass
                
                # Xpath para registro sanitario
                if not info_producto["registro_sanitario"]:
                    try:
                        reg_elements = driver.find_elements(By.XPATH, "//dt[contains(text(), 'Registro sanitario')]/following-sibling::dd[1] | //td[contains(text(), 'Registro sanitario')]/following-sibling::td[1] | //th[contains(text(), 'Registro')]/following-sibling::td[1]")
                        if reg_elements:
                            info_producto["registro_sanitario"] = reg_elements[0].text.strip()
                            logger.info(f"Registro sanitario extraído por XPath: {info_producto['registro_sanitario']}")
                    except Exception:
                        pass
                        
                # También buscar específicamente en la estructura mostrada en las capturas
                if not info_producto["laboratorio"]:
                    try:
                        lab_row = driver.find_element(By.XPATH, "//tr[td[contains(text(), 'Laboratorio')]]")
                        if lab_row:
                            cells = lab_row.find_elements(By.TAG_NAME, "td")
                            if len(cells) > 1:
                                info_producto["laboratorio"] = cells[1].text.strip()
                                logger.info(f"Laboratorio extraído de fila específica: {info_producto['laboratorio']}")
                    except:
                        pass
            except Exception as e:
                logger.warning(f"Error en búsqueda XPath: {e}")
        
        # Método 4: Buscar por texto en todo el HTML como último recurso
        if not (info_producto["laboratorio"] and info_producto["codigo_barras"] and info_producto["registro_sanitario"]):
            try:
                logger.info("Buscando información en el texto completo de la página...")
                
                # Obtener el texto completo de la página
                page_text = driver.find_element(By.TAG_NAME, "body").text.lower()
                
                # Buscar por patrones específicos
                if not info_producto["laboratorio"]:
                    patrones_lab = ["laboratorio: ", "laboratorio ", "fabricante: ", "fabricante "]
                    for patron in patrones_lab:
                        if patron in page_text:
                            inicio = page_text.find(patron) + len(patron)
                            fin = page_text.find("\n", inicio)
                            if fin == -1:
                                fin = inicio + 50  # Si no hay salto de línea, tomar 50 caracteres
                            valor = page_text[inicio:fin].strip()
                            if valor:
                                info_producto["laboratorio"] = valor
                                logger.info(f"Laboratorio extraído de texto: {valor}")
                                break
                            
                if not info_producto["codigo_barras"]:
                    patrones_codigo = ["código de barras: ", "codigo de barras: ", "ean: ", "código: "]
                    for patron in patrones_codigo:
                        if patron in page_text:
                            inicio = page_text.find(patron) + len(patron)
                            fin = page_text.find("\n", inicio)
                            if fin == -1:
                                fin = inicio + 50
                            valor = page_text[inicio:fin].strip()
                            if valor and any(c.isdigit() for c in valor):  # Verificar que al menos contenga números
                                info_producto["codigo_barras"] = valor
                                logger.info(f"Código de barras extraído de texto: {valor}")
                                break
                            
                if not info_producto["registro_sanitario"]:
                    patrones_registro = ["registro sanitario: ", "registro: ", "reg. sanitario: ", "no. registro: "]
                    for patron in patrones_registro:
                        if patron in page_text:
                            inicio = page_text.find(patron) + len(patron)
                            fin = page_text.find("\n", inicio)
                            if fin == -1:
                                fin = inicio + 50
                            valor = page_text[inicio:fin].strip()
                            if valor:
                                info_producto["registro_sanitario"] = valor
                                logger.info(f"Registro sanitario extraído de texto: {valor}")
                                break
            except Exception as e:
                logger.warning(f"Error al buscar en texto completo: {e}")
        
        # Añadir nombre_farmacia para compatibilidad con el servicio integrado
        info_producto["nombre_farmacia"] = "Sufarmed"
        
        # Verificar si se extrajo información válida
        if info_producto["nombre"]:
            logger.info("Información del producto extraída con éxito")
            # Imprimir toda la información extraída para depuración
            for campo, valor in info_producto.items():
                logger.info(f"{campo}: {valor}")
            return info_producto
        else:
            logger.warning("No se pudo extraer información válida del producto")
            return None
    
    except Exception as e:
        logger.error(f"Error general al extraer información del producto: {e}")
        return None

def buscar_producto_sufarmed(nombre_producto: str) -> dict:
    """
    Busca un producto en Sufarmed y extrae su información.
    ACTUALIZADO: Con normalización específica para Sufarmed aplicada.
    
    Args:
        nombre_producto (str): Nombre del producto YA NORMALIZADO para Sufarmed
        
    Returns:
        dict: Información del producto o None si no se encuentra
    """
    logger.info(f"Iniciando búsqueda de producto NORMALIZADO en Sufarmed: {nombre_producto}")
    
    # Configuración inicial
    headless = HEADLESS_BROWSER
    username = "laubec83@gmail.com"
    password = "Sr3ChK8pBoSEScZ"
    login_url = "https://sufarmed.com/sufarmed/iniciar-sesion"
    timeout = 15
    
    # Inicializar variables
    driver = None
    resultados = []
    
    try:
        # Inicializar el navegador
        driver = inicializar_navegador(headless)
        if not driver:
            logger.error("No se pudo inicializar el navegador, abortando búsqueda")
            return None
        
        # Verificación de funcionalidad básica
        try:
            driver.execute_script("return navigator.userAgent")
        except Exception as e:
            logger.error(f"El navegador no responde correctamente: {e}")
            if driver:
                driver.quit()
            return None
            
        # Realizar login primero para obtener precios
        logger.info("Iniciando proceso de login antes de buscar productos")
        login_exitoso = login(driver, username, password, login_url, timeout)
        
        if login_exitoso:
            logger.info("Login exitoso, procediendo con la búsqueda de productos")
        else:
            logger.warning("Login fallido, continuando sin autenticación (no se obtendrán precios)")
        
        # Acceder al sitio web principal
        logger.info(f"Accediendo al sitio web de Sufarmed...")
        driver.get("https://sufarmed.com")
        
        # Esperar a que cargue la página y buscar el campo de búsqueda
        wait = WebDriverWait(driver, 10)
        campo_busqueda = wait.until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "input[name='s']"))
        )
        
        # Ingresar el término de búsqueda NORMALIZADO
        logger.info(f"Buscando producto NORMALIZADO: {nombre_producto}")
        campo_busqueda.clear()
        campo_busqueda.send_keys(nombre_producto)
        
        # Hacer clic en el botón de búsqueda
        boton_busqueda = wait.until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "button.search-btn"))
        )
        boton_busqueda.click()
        
        # Esperar un tiempo después de hacer clic para asegurar la carga
        time.sleep(3)
        
        # Extraer y almacenar todos los enlaces que contienen el nombre del producto en su href
        all_links = driver.find_elements(By.TAG_NAME, "a")
        
        # Dividir los términos de búsqueda para hacer una coincidencia más precisa
        terminos_busqueda = [t.lower() for t in nombre_producto.split()]
        logger.info(f"Términos de búsqueda: {terminos_busqueda}")
        
        # Sistema de puntuación para enlaces
        link_scores = []
        
        for link in all_links:
            try:
                href = link.get_attribute("href") or ""
                if href and not "/module/" in href.lower() and not "javascript:" in href.lower():
                    texto_link = link.text.lower()
                    url_lower = href.lower()
                    
                    # Calcular puntaje de relevancia
                    score = 0
                    
                    # Coincidencia exacta en la URL tiene prioridad máxima
                    if nombre_producto.lower() in url_lower:
                        score += 100
                        
                    # Coincidencia de todos los términos en URL
                    if all(term in url_lower for term in terminos_busqueda):
                        score += 50
                    else:
                        # Coincidencia parcial: sumar por cada término encontrado
                        for term in terminos_busqueda:
                            if term in url_lower:
                                score += 10
                    
                    # Coincidencia en el texto visible del enlace
                    if nombre_producto.lower() in texto_link:
                        score += 30
                    elif all(term in texto_link for term in terminos_busqueda):
                        score += 20
                    else:
                        for term in terminos_busqueda:
                            if term in texto_link:
                                score += 5
                    
                    # Solo considerar enlaces con puntaje positivo
                    if score > 0:
                        link_scores.append((href, score))
                        logger.info(f"Enlace encontrado: {href}, Texto: {texto_link}, Puntaje: {score}")
            except Exception as e:
                logger.warning(f"Error al procesar enlace: {e}")
                continue
        
        # Ordenar enlaces por puntaje (mayor a menor)
        link_scores.sort(key=lambda x: x[1], reverse=True)
        
        # >>>>> CAMBIO SOLICITADO: Filtrar solo enlaces con puntuación 100 o más <<<<<
        high_score_links = [link for link in link_scores if link[1] >= 100]
        
        # Si no hay enlaces con puntuación alta, terminar
        if not high_score_links:
            logger.warning("No se encontraron enlaces con puntuación 100+, terminando búsqueda") # Mensaje actualizado
            if driver:
                driver.quit()
            return None
        
        # Usar solo los enlaces con alta puntuación
        link_scores = high_score_links
        
        # Convertir a lista de URLs
        product_links = [url for url, score in link_scores]
        
        # Eliminar duplicados preservando el orden
        product_links = list(dict.fromkeys(product_links))
        logger.info(f"Enlaces de alta relevancia (100+ puntos) encontrados: {len(product_links)}") # Mensaje actualizado
        
        # Intentar navegar a cada enlace hasta encontrar una página de producto
        for url in product_links:
            try:
                logger.info(f"Navegando a URL potencial de producto: {url}")
                driver.get(url)
                time.sleep(3)
                
                if es_pagina_producto(driver):
                    logger.info("Éxito! Página de producto encontrada.")
                    info_producto = extraer_info_producto(driver)
                    if info_producto:
                        # Añadir la clave "nombre_farmacia"
                        info_producto["nombre_farmacia"] = "Sufarmed"
                        
                        resultados.append(info_producto)
                        
                        # Si encontramos un producto con nombre que coincide exactamente, 
                        # o contiene todos los términos de búsqueda, podemos devolverlo inmediatamente
                        nombre_producto_lower = nombre_producto.lower()
                        info_nombre_lower = info_producto["nombre"].lower() if info_producto["nombre"] else ""

                        if nombre_producto_lower == info_nombre_lower or all(term in info_nombre_lower for term in terminos_busqueda):
                            logger.info(f"Encontrado producto con coincidencia exacta: {info_producto['nombre']}")
                            # Añadir log con información completa
                            logger.info(f"Información completa: Nombre: {info_producto['nombre']}, Precio: {info_producto['precio']}, Existencia: {info_producto['existencia']}")
                            return info_producto
                        
                        # Limitar a 3 resultados para no hacer la búsqueda demasiado lenta
                        if len(resultados) >= 3:
                            break
            except Exception as e:
                logger.warning(f"Error al navegar a {url}: {e}")
        
        # Si llegamos aquí y tenemos resultados, devolvemos el primero (mejor puntuado)
        if resultados:
            mejor_producto = resultados[0]
            logger.info(f"Retornando el mejor producto de {len(resultados)} encontrados")
            # Añadir log con información completa
            logger.info(f"Información completa: Nombre: {mejor_producto['nombre']}, Precio: {mejor_producto['precio']}, Existencia: {mejor_producto['existencia']}")
            return mejor_producto
            
        # Si llegamos aquí, no encontramos una página de producto válida
        logger.warning("No se pudieron encontrar enlaces de productos válidos.")
        return None
        
    except TimeoutException:
        logger.warning("Tiempo de espera agotado durante la navegación.")
        # Verificar si aún así llegamos a una página de producto
        if driver and es_pagina_producto(driver):
            logger.info("A pesar del timeout, se detectó página de producto.")
            info_producto = extraer_info_producto(driver)
            if info_producto:
                info_producto["nombre_farmacia"] = "Sufarmed"
                logger.info(f"Información completa: Nombre: {info_producto['nombre']}, Precio: {info_producto['precio']}, Existencia: {info_producto['existencia']}")
                return info_producto
    except Exception as e:
        logger.error(f"Error durante la búsqueda: {e}")
        import traceback
        logger.error(traceback.format_exc())
    finally:
        # Cerrar el navegador
        if driver:
            try:
                driver.quit()
                logger.info("Navegador cerrado correctamente")
            except Exception as e:
                logger.error(f"Error al cerrar el navegador: {e}")
    
    # Si tenemos algún resultado, devolvemos el primero
    if resultados:
        mejor_producto = resultados[0]
        # Añadir log con información completa
        logger.info(f"Información completa: Nombre: {mejor_producto['nombre']}, Precio: {mejor_producto['precio']}, Existencia: {mejor_producto['existencia']}")
        return mejor_producto
    return None

# Para pruebas directas del módulo
if __name__ == "__main__":
    import sys
    
    # Si se proporciona un argumento, usarlo como nombre del producto
    if len(sys.argv) > 1:
        nombre_producto = " ".join(sys.argv[1:])
    else:
        # Solicitar nombre del producto al usuario
        nombre_producto = input("Ingrese el nombre del producto a buscar: ")
    
    # ✅ NUEVO: Mostrar normalización
    nombre_normalizado = normalizar_busqueda_sufarmed(nombre_producto)
    print(f"\n=== NORMALIZACIÓN SUFARMED ===")
    print(f"Original: {nombre_producto}")
    print(f"Normalizado: {nombre_normalizado}")
    print("=" * 40)
    
    # Buscar información del producto
    info = buscar_producto_sufarmed(nombre_normalizado)
    
    if info:
        print("\n=== INFORMACIÓN DEL PRODUCTO ===")
        print(f"Nombre: {info['nombre']}")
        print(f"Precio: {info['precio']}")
        print(f"Existencia: {info['existencia']}")
        print(f"Disponible: {'Sí' if info.get('disponible', False) else 'No'}")
        print(f"Laboratorio: {info['laboratorio']}")
        print(f"Código de barras: {info['codigo_barras']}")
        print(f"Registro sanitario: {info['registro_sanitario']}")
        print(f"URL: {info['url']}")
        print(f"Imagen: {info['imagen']}")
    else:
        print(f"No se pudo encontrar información para el producto: {nombre_normalizado}")
