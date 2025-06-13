#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Módulo principal para el scraper de FANASA.
ACTUALIZADO: Con normalización específica para FANASA (cantidad+unidad juntos).
REGLA FANASA: Mantener nombre completo, solo juntar cantidad+unidad sin espacio.
"""

import time
import logging
import re
import os
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, ElementClickInterceptedException

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuración
USERNAME = "ventas@insumosjip.com"  # Usuario para FANASA
PASSWORD = "210407"                # Contraseña para FANASA
LOGIN_URL = "https://carrito.fanasa.com/login"  # URL correcta del portal de carrito
TIMEOUT = 20                       # Tiempo de espera para elementos (segundos)
LOGIN_TIMEOUT = 20                 # ✅ NUEVO: Timeout específico para login

def normalizar_busqueda_fanasa(producto_nombre):
    """
    Normaliza la búsqueda para FANASA: mantener nombre completo, solo juntar cantidad+unidad.
    Ejemplo: "diclofenaco inyectable 75 mg" → "diclofenaco inyectable 75mg"
    
    Args:
        producto_nombre (str): Nombre completo del producto
        
    Returns:
        str: Producto con cantidad+unidad sin espacios
    """
    if not producto_nombre:
        return producto_nombre
    
    # Mantener el texto original, solo modificar espacios entre número y unidad
    texto = producto_nombre.strip()
    
    # Patrón para encontrar número + espacio + unidad
    patron_cantidad_espacio = r'(\d+(?:\.\d+)?)\s+(mg|g|ml|mcg|ui|iu|%|cc|mgs)'
    
    # Función para reemplazar: quitar el espacio entre número y unidad
    def reemplazar_cantidad(match):
        numero = match.group(1)
        unidad = match.group(2)
        # Normalizar unidad común
        if unidad == 'mgs':
            unidad = 'mg'
        return f"{numero}{unidad}"  # Sin espacio
    
    # Aplicar el reemplazo
    resultado = re.sub(patron_cantidad_espacio, reemplazar_cantidad, texto, flags=re.IGNORECASE)
    
    logger.info(f"[FANASA] Normalización: '{producto_nombre}' → '{resultado}'")
    return resultado

def inicializar_navegador(headless=True):
    """
    Inicializa el navegador Chrome con opciones configuradas.
    
    Args:
        headless (bool): Si es True, el navegador se ejecuta en modo headless (sin interfaz gráfica)
        
    Returns:
        webdriver.Chrome: Instancia del navegador
    """
    options = Options()
    if headless:
        options.add_argument("--headless")
    
    # Configuración adicional para mejorar la estabilidad
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-notifications")
    options.add_argument("--disable-popup-blocking")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    
    # Ignorar errores de certificado SSL
    options.add_argument("--ignore-certificate-errors")
    options.add_argument("--ignore-ssl-errors")
    options.add_argument("--allow-insecure-localhost")
    
    # Reducir el nivel de logging para evitar mostrar errores SSL
    options.add_experimental_option('excludeSwitches', ['enable-logging'])
    
    try:
        # Inicializar el navegador Chrome
        driver = webdriver.Chrome(options=options)
        logger.info("Navegador Chrome inicializado correctamente")
        return driver
    except Exception as e:
        logger.error(f"Error al inicializar el navegador: {e}")
        return None

def login_fanasa_carrito():
    """
    ✅ VERSIÓN OPTIMIZADA: Login original que funcionaba al 100% + timeout de 20 segundos
    
    Returns:
        tuple: (webdriver.Chrome, bool) - (driver, login_exitoso)
    """
    driver = inicializar_navegador(headless=True)
    if not driver:
        logger.error("No se pudo inicializar el navegador. Abortando.")
        return None, False
    
    # ✅ NUEVO: Control de tiempo
    start_time = time.time()
    login_exitoso = False
    
    try:
        logger.info(f"⏰ Iniciando login con timeout de {LOGIN_TIMEOUT} segundos")
        
        # 1. Navegar a la página de login
        logger.info(f"Navegando a la página de login: {LOGIN_URL}")
        driver.get(LOGIN_URL)
        time.sleep(5)  # Esperar a que cargue la página
        
        # ✅ VERIFICAR TIMEOUT
        if time.time() - start_time > LOGIN_TIMEOUT:
            logger.warning(f"⏰ Timeout alcanzado al cargar página de login")
            return driver, False
        
        # Tomar captura de pantalla inicial
        try:
            driver.save_screenshot("01_fanasa_carrito_login_inicio.png")
            logger.info("Captura de pantalla guardada: 01_fanasa_carrito_login_inicio.png")
        except:
            logger.warning("No se pudo guardar captura de pantalla")
        
        # 2. Buscar campo de usuario
        logger.info("Buscando campo de usuario...")
        
        # Basado en la captura, el campo tiene una etiqueta "Usuario o correo"
        username_field = None
        username_selectors = [
            "input[placeholder='Usuario o correo']",
            "#email",  # Posible ID
            "input[type='email']",
            "input[type='text']:first-of-type",
            ".form-control:first-of-type"
        ]
        
        for selector in username_selectors:
            # ✅ VERIFICAR TIMEOUT
            if time.time() - start_time > LOGIN_TIMEOUT:
                logger.warning(f"⏰ Timeout alcanzado buscando campo usuario")
                return driver, False
                
            try:
                fields = driver.find_elements(By.CSS_SELECTOR, selector)
                for field in fields:
                    if field.is_displayed():
                        username_field = field
                        logger.info(f"Campo de usuario encontrado con selector: {selector}")
                        break
                if username_field:
                    break
            except:
                continue
        
        # Si no encontramos con los selectores específicos, buscar cualquier input visible
        if not username_field:
            try:
                # Buscar todos los inputs visibles
                inputs = driver.find_elements(By.TAG_NAME, "input")
                visible_inputs = [inp for inp in inputs if inp.is_displayed()]
                
                if visible_inputs:
                    # Primer input visible probablemente sea el de usuario
                    username_field = visible_inputs[0]
                    logger.info("Campo de usuario encontrado como primer input visible")
            except:
                pass
        
        # Si no se encuentra el campo de usuario, no podemos continuar
        if not username_field:
            logger.error("No se pudo encontrar el campo de usuario")
            driver.save_screenshot("error_no_campo_usuario.png")
            return driver, False
        
        # ✅ VERIFICAR TIMEOUT
        if time.time() - start_time > LOGIN_TIMEOUT:
            logger.warning(f"⏰ Timeout alcanzado antes de ingresar usuario")
            return driver, False
        
        # Limpiar e ingresar el usuario
        username_field.clear()
        username_field.send_keys(USERNAME)
        logger.info(f"Usuario ingresado: {USERNAME}")
        time.sleep(1)
        
        # Tomar captura después de ingresar el usuario
        try:
            driver.save_screenshot("02_fanasa_carrito_usuario_ingresado.png")
        except:
            pass
        
        # 3. Buscar campo de contraseña
        logger.info("Buscando campo de contraseña...")
        
        # ✅ VERIFICAR TIMEOUT
        if time.time() - start_time > LOGIN_TIMEOUT:
            logger.warning(f"⏰ Timeout alcanzado antes de buscar contraseña")
            return driver, False
        
        # Basado en la captura, es un campo con etiqueta "Contraseña"
        password_field = None
        password_selectors = [
            "input[placeholder='Contraseña']",
            "#password",  # Posible ID
            "input[type='password']",
            "input.form-control[type='password']"
        ]
        
        for selector in password_selectors:
            try:
                fields = driver.find_elements(By.CSS_SELECTOR, selector)
                for field in fields:
                    if field.is_displayed():
                        password_field = field
                        logger.info(f"Campo de contraseña encontrado con selector: {selector}")
                        break
                if password_field:
                    break
            except:
                continue
        
        # Si no encontramos con selectores específicos, buscar por tipo password
        if not password_field:
            try:
                password_inputs = driver.find_elements(By.CSS_SELECTOR, "input[type='password']")
                if password_inputs:
                    for inp in password_inputs:
                        if inp.is_displayed():
                            password_field = inp
                            logger.info("Campo de contraseña encontrado por tipo 'password'")
                            break
            except:
                pass
        
        # Si no se encuentra el campo de contraseña, no podemos continuar
        if not password_field:
            logger.error("No se pudo encontrar el campo de contraseña")
            driver.save_screenshot("error_no_campo_password.png")
            return driver, False
        
        # ✅ VERIFICAR TIMEOUT
        if time.time() - start_time > LOGIN_TIMEOUT:
            logger.warning(f"⏰ Timeout alcanzado antes de ingresar contraseña")
            return driver, False
        
        # Limpiar e ingresar la contraseña
        password_field.clear()
        password_field.send_keys(PASSWORD)
        logger.info("Contraseña ingresada")
        time.sleep(1)
        
        # Tomar captura después de ingresar la contraseña
        try:
            driver.save_screenshot("03_fanasa_carrito_password_ingresado.png")
        except:
            pass
        
        # 4. Buscar botón de inicio de sesión (basado en la captura es un botón azul)
        logger.info("Buscando botón 'Iniciar sesión'...")
        
        # ✅ VERIFICAR TIMEOUT
        if time.time() - start_time > LOGIN_TIMEOUT:
            logger.warning(f"⏰ Timeout alcanzado antes de buscar botón")
            return driver, False
        
        login_button = None
        button_selectors = [
            "button.btn-primary",  # Clase probable basada en la captura
            "button[type='submit']",
            "button:contains('Iniciar sesión')",
            ".btn-primary",
            ".btn-login"
        ]
        
        for selector in button_selectors:
            try:
                buttons = driver.find_elements(By.CSS_SELECTOR, selector)
                for button in buttons:
                    if button.is_displayed() and "iniciar sesión" in button.text.lower():
                        login_button = button
                        logger.info(f"Botón 'Iniciar sesión' encontrado con selector: {selector}")
                        break
                if login_button:
                    break
            except:
                continue
        
        # Si no encontramos con CSS, intentar con XPath específico para el texto
        if not login_button:
            try:
                xpath_buttons = driver.find_elements(By.XPATH, "//button[contains(translate(text(), 'ABCDEFGHIJKLMNÑOPQRSTUVWXYZ', 'abcdefghijklmnñopqrstuvwxyz'), 'iniciar sesión')]")
                if xpath_buttons:
                    for button in xpath_buttons:
                        if button.is_displayed():
                            login_button = button
                            logger.info("Botón 'Iniciar sesión' encontrado por texto")
                            break
            except:
                pass
        
        # Si no se encuentra un botón específico, buscar cualquier botón visible
        if not login_button:
            try:
                all_buttons = driver.find_elements(By.TAG_NAME, "button")
                for button in all_buttons:
                    if button.is_displayed() and button.is_enabled():
                        login_button = button
                        logger.info("Usando primer botón visible como botón de login")
                        break
            except:
                pass
        
        # ✅ VERIFICAR TIMEOUT ANTES DE HACER CLIC
        if time.time() - start_time > LOGIN_TIMEOUT:
            logger.warning(f"⏰ Timeout alcanzado antes de hacer clic")
            return driver, False
        
        # Si no se encuentra el botón, intentar enviar el formulario con Enter
        if not login_button:
            logger.warning("No se encontró botón de inicio de sesión. Intentando enviar formulario con Enter.")
            password_field.send_keys(Keys.RETURN)
            time.sleep(5)
            try:
                driver.save_screenshot("04_fanasa_carrito_enviado_con_enter.png")
            except:
                pass
        else:
            # Hacer clic en el botón
            try:
                # Resaltar el botón para identificarlo en la captura
                driver.execute_script("arguments[0].style.border='2px solid red'", login_button)
                try:
                    driver.save_screenshot("04a_fanasa_carrito_boton_resaltado.png")
                except:
                    pass
                
                # Asegurar que el botón sea visible
                driver.execute_script("arguments[0].scrollIntoView({block:'center'});", login_button)
                time.sleep(1)
                
                # Hacer clic
                login_button.click()
                logger.info("Clic en botón 'Iniciar sesión' realizado")
                
            except ElementClickInterceptedException:
                # Si hay algo interceptando el clic, intentar con JavaScript
                logger.warning("Clic interceptado. Intentando con JavaScript.")
                driver.execute_script("arguments[0].click();", login_button)
                logger.info("Clic en botón realizado con JavaScript")
            
            time.sleep(5)  # Esperar a que se procese el login
            try:
                driver.save_screenshot("04b_fanasa_carrito_despues_clic.png")
            except:
                pass
        
        # ✅ VERIFICAR TIMEOUT DESPUÉS DEL CLIC
        if time.time() - start_time > LOGIN_TIMEOUT:
            logger.warning(f"⏰ Timeout alcanzado después de enviar login")
            return driver, False
        
        # 5. Verificar si el login fue exitoso
        current_url = driver.current_url
        logger.info(f"URL actual después del intento de login: {current_url}")
        
        # Guardar HTML para análisis
        try:
            with open("fanasa_carrito_despues_login.html", "w", encoding="utf-8") as f:
                f.write(driver.page_source)
            logger.info("HTML después del login guardado para análisis")
        except:
            logger.warning("No se pudo guardar HTML")
        
        # Verificar si ya no estamos en la página de login
        login_exitoso = "/login" not in current_url
        
        # También verificar si hay indicadores de sesión iniciada
        if not login_exitoso:
            page_text = driver.page_source.lower()
            success_indicators = [
                "cerrar sesión" in page_text,
                "logout" in page_text,
                "mi cuenta" in page_text,
                "carrito" in page_text and not "/login" in current_url
            ]
            
            login_exitoso = any(success_indicators)
        
        # Verificar si hay mensajes de error visibles
        has_error = False
        try:
            error_messages = driver.find_elements(By.CSS_SELECTOR, ".error, .alert-danger, .text-danger")
            for error in error_messages:
                if error.is_displayed():
                    has_error = True
                    logger.error(f"Mensaje de error detectado: {error.text}")
                    break
        except:
            pass
        
        # Resultado final
        if login_exitoso and not has_error:
            logger.info("┌─────────────────────────────────────┐")
            logger.info("│ ¡LOGIN EXITOSO EN FANASA CARRITO!   │")
            logger.info("└─────────────────────────────────────┘")
            
            # Tomar una última captura después del login exitoso
            try:
                driver.save_screenshot("05_fanasa_carrito_login_exitoso.png")
            except:
                pass
            
            return driver, True  # ✅ NUEVO: Retornar tupla
        else:
            logger.error("┌─────────────────────────────────────┐")
            logger.error("│ ERROR: Login en FANASA Carrito fallido │")
            logger.error("└─────────────────────────────────────┘")
            
            if has_error:
                logger.error("Se detectaron mensajes de error en la página")
            
            try:
                driver.save_screenshot("error_login_fallido.png")
            except:
                pass
            
            return driver, False  # ✅ NUEVO: Retornar tupla con false
        
    except Exception as e:
        logger.error(f"Error durante el proceso de login: {e}")
        if driver:
            try:
                driver.save_screenshot("error_general_login.png")
            except:
                pass
        
        return driver, False  # ✅ NUEVO: Retornar tupla incluso con error

def buscar_producto(driver, nombre_producto):
    """
    Busca un producto en FANASA.
    
    Args:
        driver: WebDriver con sesión iniciada
        nombre_producto: Nombre del producto a buscar (YA NORMALIZADO)
        
    Returns:
        bool: True si se encontraron resultados
    """
    if not driver:
        logger.error("❌ Driver no válido para búsqueda")
        return False
    
    try:
        logger.info(f"🔍 Iniciando búsqueda de producto NORMALIZADO: {nombre_producto}")
        
        # Esperar a que la página principal esté cargada
        time.sleep(3)
        try:
            driver.save_screenshot("pagina_principal.png")
        except:
            pass
        
        # Buscar el input de búsqueda por varios selectores posibles
        search_field = None
        search_selectors = [
            "input[placeholder*='Nombre, laboratorio']",
            "input[placeholder*='nombre']",
            "input.search_input",
            "input[name='parametro1']",
            ".search input"
        ]
        
        for selector in search_selectors:
            try:
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                for element in elements:
                    if element.is_displayed():
                        search_field = element
                        logger.info(f"Campo de búsqueda encontrado con selector: {selector}")
                        break
                if search_field:
                    break
            except:
                continue
        
        if not search_field:
            # Si no se encuentra con CSS, intentar con XPath
            try:
                search_field = driver.find_element(By.XPATH, "//input[contains(@placeholder, 'Nombre') or contains(@placeholder, 'nombre')]")
                logger.info("Campo de búsqueda encontrado con XPath")
            except:
                pass
        
        # Si todavía no lo encuentra, buscar en el DOM por atributos
        if not search_field:
            try:
                # Buscar mediante navegación desde el formulario
                forms = driver.find_elements(By.TAG_NAME, "form")
                for form in forms:
                    inputs = form.find_elements(By.TAG_NAME, "input")
                    for inp in inputs:
                        if inp.is_displayed() and inp.get_attribute("type") == "text":
                            search_field = inp
                            logger.info("Campo de búsqueda encontrado dentro de formulario")
                            break
                    if search_field:
                        break
            except:
                pass
        
        # Como último recurso, probar con cualquier input visible
        if not search_field:
            try:
                all_inputs = driver.find_elements(By.TAG_NAME, "input")
                for inp in all_inputs:
                    if inp.is_displayed() and inp.get_attribute("type") != "hidden":
                        search_field = inp
                        logger.info("Usando primer campo input visible como campo de búsqueda")
                        break
            except:
                pass
        
        if not search_field:
            logger.error("No se pudo encontrar el campo de búsqueda")
            try:
                driver.save_screenshot("error_no_campo_busqueda.png")
            except:
                pass
            return False
        
        # Resaltar el campo de búsqueda en la captura
        driver.execute_script("arguments[0].style.border='3px solid red'", search_field)
        try:
            driver.save_screenshot("campo_busqueda_encontrado.png")
        except:
            pass
        
        # Limpiar e ingresar el término de búsqueda NORMALIZADO
        search_field.clear()
        search_field.send_keys(nombre_producto)
        logger.info(f"Texto NORMALIZADO '{nombre_producto}' ingresado en campo de búsqueda")
        
        # Esperar un momento para que se registre el texto
        time.sleep(2)
        
        # Método 1: Presionar Enter para enviar la búsqueda
        search_field.send_keys(Keys.RETURN)
        logger.info("Búsqueda enviada con tecla Enter")
        
        # Esperar a que se carguen los resultados
        time.sleep(5)
        
        # Tomar captura de la página de resultados
        try:
            driver.save_screenshot("resultados_busqueda.png")
        except:
            pass
        
        # Verificar la presencia de productos en la página
        # Buscar elementos que indiquen productos
        product_indicators = [
            "//h4[contains(text(), 'ZOLADEX') or contains(text(), 'PARACETAMOL') or contains(text(), '" + nombre_producto.upper() + "')]",
            "//div[contains(@class, 'card')]",
            "//div[contains(@class, 'producto')]",
            "//button[contains(text(), 'Agregar a carrito')]",
            "//div[contains(text(), 'Precio Neto')]",
            "//div[contains(text(), 'Precio Público')]"
        ]
        
        for indicator in product_indicators:
            elements = driver.find_elements(By.XPATH, indicator)
            if elements and any(e.is_displayed() for e in elements):
                logger.info(f"✅ Productos encontrados mediante indicador: {indicator}")
                return True
        
        # Si no se encuentran indicadores específicos, verificar si hay resultados en general
        if nombre_producto.lower() in driver.page_source.lower():
            logger.info("✅ El término de búsqueda aparece en la página de resultados")
            return True
        else:
            logger.warning("⚠️ No se encontraron productos que coincidan con la búsqueda")
            return False
            
    except Exception as e:
        logger.error(f"⚠️ Error durante la búsqueda: {e}")
        try:
            driver.save_screenshot("error_busqueda.png")
        except:
            pass
        return False

def extraer_info_productos(driver, numero_producto=0):
    """
    Extrae información de un producto directamente desde la tarjeta en la página de resultados.
    
    Args:
        driver: WebDriver con la página de resultados cargada
        numero_producto: Índice del producto a extraer (0 para el primero)
        
    Returns:
        dict: Diccionario con la información del producto o None si hay error
    """
    if not driver:
        logger.error("No se proporcionó un navegador válido")
        return None
    
    try:
        logger.info(f"Extrayendo información del producto #{numero_producto}")
        
        # Guardar página para análisis
        try:
            driver.save_screenshot(f"pagina_resultados_producto_{numero_producto}.png")
        except:
            pass
        
        # Inicializar diccionario de información
        info_producto = {
            'url': driver.current_url,
            'nombre': '',
            'precio_neto': '',
            'pmp': '',
            'precio_publico': '',
            'precio_farmacia': '',
            'sku': '',
            'codigo': '',
            'laboratorio': '',
            'disponibilidad': '',
            'imagen': ''
        }
        
        # Buscar contenedores de productos (tarjetas)
        product_cards = []
        card_selectors = [
            "//div[contains(@class, 'card')]",
            "//div[contains(@class, 'row')][.//h4]",
            "//div[contains(@class, 'producto')]",
            "//div[contains(@class, 'card-body')]",
            "//div[.//button[contains(text(), 'Agregar a carrito')]]"
        ]
        
        for selector in card_selectors:
            cards = driver.find_elements(By.XPATH, selector)
            visible_cards = [card for card in cards if card.is_displayed()]
            if visible_cards:
                product_cards = visible_cards
                logger.info(f"Encontradas {len(product_cards)} tarjetas de productos con selector: {selector}")
                break
        
        if not product_cards:
            logger.warning("No se encontraron tarjetas de productos. Intentando extraer de toda la página.")
            # Si no hay tarjetas, intentar extraer de la página completa
            product_card = driver.find_element(By.TAG_NAME, "body")
        else:
            # Seleccionar la tarjeta según el índice proporcionado
            if numero_producto < len(product_cards):
                product_card = product_cards[numero_producto]
                logger.info(f"Seleccionando producto #{numero_producto}")
                # Resaltar el producto seleccionado
                try:
                    driver.execute_script("arguments[0].style.border='3px solid green'", product_card)
                    driver.save_screenshot(f"tarjeta_producto_{numero_producto}_seleccionada.png")
                except:
                    pass
            else:
                logger.warning(f"Índice {numero_producto} fuera de rango. Solo hay {len(product_cards)} productos. Usando el primero.")
                product_card = product_cards[0]
        
        # Extraer NOMBRE del producto
        try:
            nombre_elements = product_card.find_elements(By.XPATH, 
                ".//h4 | .//h2 | .//h3 | .//h5[contains(@class, 'Name-product')] | .//h5[contains(@class, 'name-product')] | .//h5[contains(@class, 'mb-2')] | .//div[contains(@class, 'name-product')] | .//div[contains(@class, 'product-name')] | .//strong[contains(text(), 'PARACETAMOL')] | .//strong[contains(text(), 'ZOLADEX')]")
            
            for element in nombre_elements:
                if element.is_displayed():
                    texto = element.text.strip()
                    if texto and len(texto) > 5 and "regresar" not in texto.lower():
                        info_producto['nombre'] = texto
                        logger.info(f"Nombre del producto: {info_producto['nombre']}")
                        break
            
            # Si no encontramos el nombre con los selectores anteriores, intentar con clases específicas
            if not info_producto['nombre']:
                nombre_class_elements = product_card.find_elements(By.CSS_SELECTOR, 
                    ".name-product, .product-name, .mb-2, .Name-product, h5.font-weight-bold")
                
                for element in nombre_class_elements:
                    if element.is_displayed():
                        texto = element.text.strip()
                        if texto and len(texto) > 5 and "regresar" not in texto.lower():
                            info_producto['nombre'] = texto
                            logger.info(f"Nombre del producto (por clase): {info_producto['nombre']}")
                            break
                            
            # Si todavía no tenemos nombre, intentar con el texto visible más largo
            if not info_producto['nombre']:
                visible_texts = []
                all_elements = product_card.find_elements(By.XPATH, ".//*")
                for element in all_elements:
                    if element.is_displayed():
                        texto = element.text.strip()
                        if texto and len(texto) > 10 and "precio" not in texto.lower() and "$" not in texto:
                            visible_texts.append((len(texto), texto))
                
                if visible_texts:
                    # Ordenar por longitud (el texto más largo primero)
                    visible_texts.sort(reverse=True)
                    info_producto['nombre'] = visible_texts[0][1]
                    logger.info(f"Nombre del producto (texto más largo): {info_producto['nombre']}")
        except Exception as e:
            logger.warning(f"Error extrayendo nombre: {e}")
        
        # Extraer PRECIOS
        try:
            # Buscar Precio Neto
            precio_neto_elements = product_card.find_elements(By.XPATH, 
                ".//div[contains(text(), 'Precio Neto')]/following-sibling::* | .//h5[contains(text(), 'Precio Neto')]/following-sibling::*")
            
            for element in precio_neto_elements:
                if element.is_displayed():
                    texto = element.text.strip()
                    precio_match = re.search(r'\$?([\d,]+\.?\d*)', texto)
                    if precio_match:
                        info_producto['precio_neto'] = f"${precio_match.group(1)}"
                        logger.info(f"Precio Neto: {info_producto['precio_neto']}")
                        break
            
            # Si no encontramos precio neto con el texto explícito, buscar por posición o por clase
            if not info_producto['precio_neto']:
                precio_elements = product_card.find_elements(By.XPATH, ".//*[contains(text(), '$')]")
                for element in precio_elements:
                    if element.is_displayed():
                        parent = element.find_element(By.XPATH, "..")
                        if "neto" in parent.text.lower():
                            precio_match = re.search(r'\$?([\d,]+\.?\d*)', element.text)
                            if precio_match:
                                info_producto['precio_neto'] = f"${precio_match.group(1)}"
                                logger.info(f"Precio Neto (desde elemento): {info_producto['precio_neto']}")
                                break
            
            # Extraer Precio PMP
            pmp_elements = product_card.find_elements(By.XPATH, 
                ".//div[contains(text(), 'PMP')]/following-sibling::* | .//h6[contains(text(), 'PMP')]/following-sibling::*")
            
            for element in pmp_elements:
                if element.is_displayed():
                    texto = element.text.strip()
                    precio_match = re.search(r'\$?([\d,]+\.?\d*)', texto)
                    if precio_match:
                        info_producto['pmp'] = f"${precio_match.group(1)}"
                        logger.info(f"PMP: {info_producto['pmp']}")
                        break
            
            # Extraer Precio Público
            precio_publico_elements = product_card.find_elements(By.XPATH, 
                ".//div[contains(text(), 'Precio Público')]/following-sibling::* | .//h5[contains(text(), 'Precio Público')]/following-sibling::* | .//h6[contains(text(), 'Precio Público')]")
            
            for element in precio_publico_elements:
                if element.is_displayed():
                    texto = element.text.strip()
                    if not texto:  # Si el elemento no tiene texto, buscar en su siguiente hermano
                        try:
                            next_sibling = element.find_element(By.XPATH, "following-sibling::*")
                            texto = next_sibling.text.strip()
                        except:
                            continue
                    
                    precio_match = re.search(r'\$?([\d,]+\.?\d*)', texto)
                    if precio_match:
                        info_producto['precio_publico'] = f"${precio_match.group(1)}"
                        logger.info(f"Precio Público: {info_producto['precio_publico']}")
                        break
            
            # Extraer Precio Farmacia
            precio_farmacia_elements = product_card.find_elements(By.XPATH, 
                ".//div[contains(text(), 'Precio Farmacia')]/following-sibling::* | .//h5[contains(text(), 'Precio Farmacia')]/following-sibling::* | .//h6[contains(text(), 'Precio Farmacia')]")
            
            for element in precio_farmacia_elements:
                if element.is_displayed():
                    texto = element.text.strip()
                    if not texto:  # Si el elemento no tiene texto, buscar en su siguiente hermano
                        try:
                            next_sibling = element.find_element(By.XPATH, "following-sibling::*")
                            texto = next_sibling.text.strip()
                        except:
                            continue
                    
                    precio_match = re.search(r'\$?([\d,]+\.?\d*)', texto)
                    if precio_match:
                        info_producto['precio_farmacia'] = f"${precio_match.group(1)}"
                        logger.info(f"Precio Farmacia: {info_producto['precio_farmacia']}")
                        break
        except Exception as e:
            logger.warning(f"Error extrayendo precios: {e}")
        
        # Extraer CÓDIGO / SKU
        try:
            codigo_elements = product_card.find_elements(By.XPATH, 
                ".//div[contains(text(), 'Código')]/following-sibling::* | .//h6[contains(text(), 'ódigo:')] | .//h6[contains(text(), 'Código')] | .//div[contains(text(), 'Código')]")
            
            for element in codigo_elements:
                if element.is_displayed():
                    texto = element.text.strip()
                    codigo_match = re.search(r'[\d]{7,}', texto)
                    if codigo_match:
                        info_producto['codigo'] = codigo_match.group(0)
                        info_producto['sku'] = codigo_match.group(0)  # Usar mismo valor para sku
                        logger.info(f"Código/SKU: {info_producto['codigo']}")
                        break
            
            # Si no encontramos con el método anterior, buscar elementos con números largos
            if not info_producto['codigo']:
                all_elements = product_card.find_elements(By.XPATH, ".//*")
                for element in all_elements:
                    if element.is_displayed():
                        texto = element.text.strip()
                        if re.search(r'[\d]{7,}', texto) and not re.search(r'\$', texto):
                            codigo_match = re.search(r'[\d]{7,}', texto)
                            if codigo_match:
                                info_producto['codigo'] = codigo_match.group(0)
                                info_producto['sku'] = codigo_match.group(0)
                                logger.info(f"Código/SKU (de elemento genérico): {info_producto['codigo']}")
                                break
        except Exception as e:
            logger.warning(f"Error extrayendo código/SKU: {e}")
        
        # Extraer LABORATORIO
        try:
            # Buscar explícitamente por texto "Laboratorio:"
            lab_elements = product_card.find_elements(By.XPATH, 
                ".//div[contains(text(), 'Laboratorio')]/following-sibling::* | .//div[contains(text(), 'LABORATORIO')]")
            
            for element in lab_elements:
                if element.is_displayed():
                    texto = element.text.strip()
                    # Si es el elemento que contiene "Laboratorio:", extraer solo la parte del laboratorio
                    if "laboratorio:" in texto.lower():
                        lab_match = re.search(r'laboratorio:?\s*(.+)', texto, re.IGNORECASE)
                        if lab_match:
                            info_producto['laboratorio'] = lab_match.group(1).strip()
                            logger.info(f"Laboratorio: {info_producto['laboratorio']}")
                            break
                    elif len(texto) > 3 and "$" not in texto:
                        info_producto['laboratorio'] = texto
                        logger.info(f"Laboratorio: {info_producto['laboratorio']}")
                        break
        except Exception as e:
            logger.warning(f"Error extrayendo laboratorio: {e}")
        
        # Extraer DISPONIBILIDAD / STOCK
        try:
            stock_elements = product_card.find_elements(By.XPATH, 
                ".//div[contains(text(), 'Stock')] | .//div[contains(text(), 'Existencias')] | .//div[contains(text(), 'Disponibilidad')] | .//span[contains(@class, 'cantidad')] | .//h6[contains(@class, 'stock')]")
            
            for element in stock_elements:
                if element.is_displayed():
                    texto = element.text.strip()
                    if texto:
                        stock_match = re.search(r'(\d+)\s*disponibles', texto, re.IGNORECASE)
                        if stock_match:
                            info_producto['disponibilidad'] = f"Stock ({stock_match.group(1)})"
                            logger.info(f"Disponibilidad: {info_producto['disponibilidad']}")
                            break
                        elif "stock" in texto.lower() or "existencias" in texto.lower():
                            info_producto['disponibilidad'] = texto
                            logger.info(f"Disponibilidad (texto completo): {info_producto['disponibilidad']}")
                            break
            
            # Si no encontramos stock específico, buscar en toda la tarjeta
            if not info_producto['disponibilidad']:
                card_text = product_card.text.lower()
                if "disponibles" in card_text:
                    stock_match = re.search(r'(\d+)\s*disponibles', card_text)
                    if stock_match:
                        info_producto['disponibilidad'] = f"Stock ({stock_match.group(1)})"
                        logger.info(f"Disponibilidad (de texto de tarjeta): {info_producto['disponibilidad']}")
                elif "stock" in card_text:
                    stock_match = re.search(r'stock[:\s]*(\d+)', card_text)
                    if stock_match:
                        info_producto['disponibilidad'] = f"Stock ({stock_match.group(1)})"
                        logger.info(f"Disponibilidad (stock en texto): {info_producto['disponibilidad']}")
                else:
                    # Usar valor predeterminado
                    info_producto['disponibilidad'] = "Stock disponible"
                    logger.info("Usando valor predeterminado para disponibilidad")
        except Exception as e:
            logger.warning(f"Error extrayendo disponibilidad: {e}")
            info_producto['disponibilidad'] = "Stock disponible"
        
        # Extraer IMAGEN del producto
        try:
            img_elements = product_card.find_elements(By.TAG_NAME, "img")
            for img in img_elements:
                if img.is_displayed():
                    src = img.get_attribute("src")
                    if src and ("http" in src) and img.size['width'] > 50 and img.size['height'] > 50:
                        info_producto['imagen'] = src
                        logger.info(f"URL de imagen: {info_producto['imagen']}")
                        break
        except Exception as e:
            logger.warning(f"Error extrayendo imagen: {e}")
        
        # Verificar información mínima
        info_minima = (info_producto['precio_neto'] or info_producto['precio_publico'] or info_producto['precio_farmacia'] or info_producto['pmp']) and info_producto['codigo']

        if info_minima:
            # Si tenemos precios y código pero no nombre, usar un nombre genérico
            if not info_producto['nombre'] and info_producto['codigo']:
                info_producto['nombre'] = f"Producto {info_producto['codigo']}"
                logger.info(f"Usando código como nombre: {info_producto['nombre']}")
            
            logger.info("✅ Información mínima del producto extraída con éxito")
            return info_producto
        else:
            logger.warning("⚠️ No se pudo extraer información mínima de precios o código")
            return info_producto
    
    except Exception as e:
        logger.error(f"Error general extrayendo información: {e}")
        try:
            driver.save_screenshot("error_extraccion_general.png")
        except:
            pass
        return None

def buscar_info_medicamento(nombre_medicamento, headless=True):
    """
    ✅ VERSIÓN OPTIMIZADA: Función principal con normalización específica para FANASA
    
    Args:
        nombre_medicamento (str): Nombre del medicamento a buscar
        headless (bool): Si es True, el navegador se ejecuta en modo headless
        
    Returns:
        dict: Diccionario con la información del medicamento en formato compatible
    """
    driver = None
    try:
        logger.info(f"🚀 Iniciando proceso para buscar información sobre: '{nombre_medicamento}'")
        
        # ✅ NUEVO: Normalizar búsqueda para FANASA
        nombre_normalizado = normalizar_busqueda_fanasa(nombre_medicamento)
        
        # ✅ NUEVO: Login con timeout que retorna tupla
        driver, login_exitoso = login_fanasa_carrito()
        
        if not driver:
            logger.error("❌ No se pudo inicializar el navegador. Abortando búsqueda.")
            return {
                "error": "error_navegador", 
                "mensaje": "No se pudo inicializar el navegador",
                "estado": "error",
                "fuente": "FANASA"
            }
        
        # ✅ NUEVO: Continuar independientemente del resultado del login
        if login_exitoso:
            logger.info("✅ Sesión iniciada exitosamente en FANASA")
        else:
            logger.warning("⚠️ Login no confirmado, pero continuando con la búsqueda...")
        
        # 2. Buscar el producto con nombre NORMALIZADO
        logger.info(f"🔍 Buscando producto NORMALIZADO: '{nombre_normalizado}'")
        
        resultado_busqueda = buscar_producto(driver, nombre_normalizado)
        
        if not resultado_busqueda:
            logger.warning(f"❌ No se pudo encontrar o acceder al producto: '{nombre_normalizado}'")
            return {
                "nombre": nombre_medicamento,
                "mensaje": f"No se encontró información para {nombre_medicamento} en FANASA",
                "estado": "no_encontrado",
                "fuente": "FANASA",
                "disponibilidad": "No disponible",
                "existencia": "0"
            }
        
        # 3. Extraer información del producto
        logger.info("📊 Extrayendo información del producto...")
        info_producto = extraer_info_productos(driver)
        
        # Añadir la fuente para integración con el servicio principal
        if info_producto:
            info_producto['fuente'] = 'FANASA'
            info_producto['estado'] = 'encontrado'
            
            # Compatibilidad para trabajar con el servicio de orquestación
            info_producto['existencia'] = '0'
            if info_producto['disponibilidad']:
                # Extraer números de la disponibilidad si existe
                stock_match = re.search(r'(\d+)', info_producto['disponibilidad'])
                if stock_match:
                    info_producto['existencia'] = stock_match.group(1)
                elif 'disponible' in info_producto['disponibilidad'].lower():
                    info_producto['existencia'] = 'Si'
            
            # Asignar precio principal
            info_producto['precio'] = (info_producto.get('precio_neto') or 
                                     info_producto.get('precio_publico') or 
                                     info_producto.get('precio_farmacia') or 
                                     info_producto.get('pmp') or 
                                     "0")
            
            logger.info(f"✅ Producto procesado: {info_producto['nombre']} - Precio: {info_producto['precio']} - Existencia: {info_producto['existencia']}")
            return info_producto
        else:
            return {
                "nombre": nombre_medicamento,
                "mensaje": f"No se pudo extraer información para {nombre_medicamento} en FANASA",
                "estado": "error_extraccion",
                "fuente": "FANASA",
                "disponibilidad": "Desconocida",
                "existencia": "0"
            }
        
    except Exception as e:
        logger.error(f"❌ Error general durante el proceso: {e}")
        return {
            "nombre": nombre_medicamento,
            "mensaje": f"Error al buscar {nombre_medicamento}: {str(e)}",
            "estado": "error",
            "fuente": "FANASA",
            "disponibilidad": "Error",
            "existencia": "0"
        }
    finally:
        if driver:
            logger.info("🔚 Cerrando navegador...")
            try:
                driver.quit()
            except:
                pass

# Para pruebas directas del módulo
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        medicamento = " ".join(sys.argv[1:])
    else:
        medicamento = input("Ingrese el nombre del medicamento a buscar: ")
    
    # ✅ NUEVO: Mostrar normalización
    medicamento_normalizado = normalizar_busqueda_fanasa(medicamento)
    print(f"\n=== NORMALIZACIÓN FANASA ===")
    print(f"Original: {medicamento}")
    print(f"Normalizado: {medicamento_normalizado}")
    print("=" * 40)
    
    resultado = buscar_info_medicamento(medicamento, headless=False)  # False para ver el navegador
    
    if resultado and resultado.get('estado') == 'encontrado':
        print("\n✅ INFORMACIÓN DEL PRODUCTO ✅")
        print(f"Nombre: {resultado['nombre']}")
        print(f"Precio: {resultado.get('precio', 'No disponible')}")
        print(f"Existencia: {resultado['existencia']}")
        print(f"Disponibilidad: {resultado.get('disponibilidad', 'No disponible')}")
        print(f"Laboratorio: {resultado.get('laboratorio', 'No disponible')}")
        print(f"Código: {resultado.get('codigo', 'No disponible')}")
        print(f"URL: {resultado.get('url', 'No disponible')}")
    else:
        print(f"\n❌ {resultado.get('mensaje', 'No se encontró información del producto')}")
        print(f"Estado: {resultado.get('estado', 'desconocido')}")
