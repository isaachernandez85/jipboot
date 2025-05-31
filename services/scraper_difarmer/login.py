"""
Módulo de login optimizado para entornos de Cloud Run.
Maneja el inicio de sesión en Difarmer con la configuración correcta para navegadores headless.
"""
import time
import logging
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from webdriver_manager.chrome import ChromeDriverManager

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuración
USERNAME = "C20118"  # Usuario para Difarmer
PASSWORD = "7913"    # Contraseña para Difarmer
BASE_URL = "https://www.difarmer.com"  # URL base del sitio
TIMEOUT = 15  # Tiempo máximo de espera para elementos (segundos)

def inicializar_navegador(headless=True):
    """
    Inicializa el navegador Chrome con opciones configuradas para entorno de servidor.
  
    Args:
        headless (bool): Si es True, el navegador se ejecuta en modo headless (sin interfaz gráfica)
       
    Returns:
        webdriver.Chrome: Instancia del navegador
    """
    options = Options()
    
    # Forzar modo headless en entorno de servidor
    if headless:
        # Configuración headless mejorada para Chrome más reciente
        options.add_argument("--headless=new")
    
    # Configuración adicional para entorno sin interfaz gráfica
    options.add_argument("--no-sandbox")  # Necesario para ejecutar como root en contenedores
    options.add_argument("--disable-dev-shm-usage")  # Evita errores de memoria compartida
    options.add_argument("--disable-gpu")  # Necesario para algunos sistemas
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-notifications")
    options.add_argument("--disable-popup-blocking")
    
    # Configuración adicional para evitar errores comunes
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-setuid-sandbox")
    options.add_argument("--remote-debugging-port=9222")  # Para debugging si es necesario
    
    # Configuración de seguridad y estabilidad
    options.add_argument("--no-first-run")
    options.add_argument("--no-default-browser-check")
    options.add_argument("--disable-blink-features=AutomationControlled")  # Evitar detección de automatización
    
    # Configuración de rendimiento
    options.add_argument("--disable-infobars")
    options.add_argument("--disable-browser-side-navigation")
    options.add_argument("--dns-prefetch-disable")
    
    # Log level para debugging
    options.add_argument("--log-level=1")  # VERBOSE logging
    
    # Configuración para entornos sin GUI
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-software-rasterizer")
    
    try:
        # Inicializar el navegador Chrome con service
        logger.info("===== WebDriver manager =====")
        
        try:
            # Instalar y usar el driver con webdriver-manager
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=options)
            logger.info("Navegador Chrome inicializado correctamente con webdriver-manager")
        except Exception as e:
            # Si falla, intentar con la ubicación predeterminada de Chrome en sistemas Linux
            logger.warning(f"Error al inicializar con webdriver-manager: {e}")
            logger.info("Intentando inicializar con ubicación predeterminada...")
            
            # Configuración para Chrome en ruta estándar de Docker/Cloud Run
            options.binary_location = "/usr/bin/google-chrome"
            
            # Inicializar con el service de Chrome
            service = Service()
            driver = webdriver.Chrome(service=service, options=options)
            logger.info("Navegador Chrome inicializado correctamente con ubicación predeterminada")
            
        # Establecer timeout global
        driver.set_page_load_timeout(TIMEOUT)
        driver.implicitly_wait(TIMEOUT)
        
        return driver
    except Exception as e:
        logger.error(f"Error al inicializar el navegador: {e}")
        return None

def login_difarmer(headless=True):
    """
    Realiza el proceso de login en el sitio web de Difarmer.
   
    Args:
        headless (bool): Si es True, el navegador se ejecuta en modo headless
        
    Returns:
        webdriver.Chrome: Instancia del navegador con sesión iniciada o None si falla
    """
    # Intentar con un máximo de 3 intentos
    max_intentos = 3
    for intento in range(1, max_intentos+1):
        logger.info(f"Intento de login #{intento}")
        
        driver = inicializar_navegador(headless=headless)
        if not driver:
            logger.error("No se pudo inicializar el navegador. Abortando.")
            continue  # Intentar de nuevo
        
        try:
            # 1. Navegar a la página principal
            logger.info(f"Navegando a: {BASE_URL}")
            driver.get(BASE_URL)
            time.sleep(5)  # Esperar a que cargue la página completamente
            
            # Tomar una captura para debugging
            driver.save_screenshot(f"home_page_{intento}.png")
            
            # 2. Buscar y hacer clic en el botón "Iniciar Sesion"
            try:
                logger.info("Buscando botón 'Iniciar Sesion'...")
                
                # Buscar por el texto específico "Iniciar Sesion" o variaciones
                xpaths_login = [
                    "//button[contains(., 'Iniciar Sesion')]",
                    "//a[contains(., 'Iniciar Sesion')]",
                    "//button[contains(., 'Iniciar Sesión')]",
                    "//a[contains(., 'Iniciar Sesión')]",
                    "//*[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'iniciar sesion')]"
                ]
                
                login_button = None
                for xpath in xpaths_login:
                    elementos = driver.find_elements(By.XPATH, xpath)
                    if elementos:
                        login_button = elementos[0]
                        logger.info(f"Botón 'Iniciar Sesion' encontrado con XPath: {xpath}")
                        break
                
                # Si no encontramos por XPath, buscar por clase CSS
                if not login_button:
                    css_selectors = [
                        ".btn-primary", 
                        ".btn-login", 
                        ".login-button", 
                        "button.blue-button", 
                        ".difarmer-login-button"
                    ]
                    
                    for selector in css_selectors:
                        elementos = driver.find_elements(By.CSS_SELECTOR, selector)
                        if elementos:
                            login_button = elementos[0]
                            logger.info(f"Botón 'Iniciar Sesion' encontrado con selector CSS: {selector}")
                            break
                
                # Si encontramos el botón, hacer clic
                if login_button:
                    # Hacer clic con JavaScript para mayor compatibilidad
                    driver.execute_script("arguments[0].click();", login_button)
                    logger.info("Clic en 'Iniciar Sesion' realizado con JavaScript")
                    time.sleep(3)  # Esperar a que aparezca el modal de login
                    
                    # Tomar captura después del clic
                    driver.save_screenshot(f"after_login_click_{intento}.png")
                else:
                    logger.warning("No se encontró botón 'Iniciar Sesion'. Verificando si ya estamos en la página de login...")
            
            except Exception as e:
                logger.warning(f"Error al buscar/hacer clic en botón de 'Iniciar Sesion': {e}")
                logger.info("Intentando continuar asumiendo que ya estamos en la página de login...")
            
            # 3. Buscar campo de usuario
            try:
                # Esperar un momento para que cargue el modal
                time.sleep(3)
            
                logger.info("Buscando campo de usuario...")
                
                # Intentar varias estrategias para encontrar el campo de usuario
                usuario_input = None
                
                # Método 1: Buscar por CSS selector específico
                username_selectors = [
                    "input[placeholder='Usuario']",
                    "input[name='username']",
                    "input[id='user']",
                    "input[id='username']",
                    "input[id='email']",
                    "input.username-field"
                ]
                
                for selector in username_selectors:
                    elementos = driver.find_elements(By.CSS_SELECTOR, selector)
                    if elementos and elementos[0].is_displayed():
                        usuario_input = elementos[0]
                        logger.info(f"Campo de usuario encontrado con selector: {selector}")
                        break
                
                # Método 2: Buscar por XPath con texto de label
                if not usuario_input:
                    xpath_username = [
                        "//label[text()='Usuario']/following::input[1]",
                        "//div[text()='Usuario']/following::input[1]",
                        "//label[contains(text(), 'Usuario')]/following::input[1]"
                    ]
                    
                    for xpath in xpath_username:
                        try:
                            elementos = driver.find_elements(By.XPATH, xpath)
                            if elementos and elementos[0].is_displayed():
                                usuario_input = elementos[0]
                                logger.info(f"Campo de usuario encontrado con XPath: {xpath}")
                                break
                        except:
                            pass
                
                # Método 3: Buscar el primer campo de entrada visible
                if not usuario_input:
                    all_inputs = driver.find_elements(By.CSS_SELECTOR, "input[type='text'], input:not([type])")
                    for input_field in all_inputs:
                        if input_field.is_displayed():
                            usuario_input = input_field
                            logger.info("Campo de usuario encontrado (primer campo visible)")
                            break
                
                # Si encontramos el campo, ingresar el usuario
                if usuario_input:
                    usuario_input.clear()
                    usuario_input.send_keys(USERNAME)
                    logger.info(f"Usuario ingresado: {USERNAME}")
                else:
                    logger.error("No se pudo encontrar el campo de usuario")
                    driver.save_screenshot(f"error_no_campo_usuario_{intento}.png")
                    driver.quit()
                    continue  # Intentar de nuevo
                
                # 4. Buscar campo de contraseña
                logger.info("Buscando campo de contraseña...")
                
                password_input = None
                
                # Método 1: Buscar por tipo password
                password_fields = driver.find_elements(By.CSS_SELECTOR, "input[type='password']")
                if password_fields:
                    for field in password_fields:
                        if field.is_displayed():
                            password_input = field
                            logger.info("Campo de contraseña encontrado por tipo 'password'")
                            break
                
                # Método 2: Buscar por placeholder
                if not password_input:
                    pwd_selectors = [
                        "input[placeholder='Contraseña']",
                        "input[placeholder='Password']",
                        "input[name='password']",
                        "input[id='password']",
                        "input[id='passwd']"
                    ]
                    
                    for selector in pwd_selectors:
                        elementos = driver.find_elements(By.CSS_SELECTOR, selector)
                        if elementos and elementos[0].is_displayed():
                            password_input = elementos[0]
                            logger.info(f"Campo de contraseña encontrado con selector: {selector}")
                            break
                
                # Método 3: Buscar por XPath con texto de label
                if not password_input:
                    xpath_password = [
                        "//label[text()='Contraseña']/following::input[1]",
                        "//div[text()='Contraseña']/following::input[1]",
                        "//label[contains(text(), 'Contraseña')]/following::input[1]"
                    ]
                    
                    for xpath in xpath_password:
                        try:
                            elementos = driver.find_elements(By.XPATH, xpath)
                            if elementos and elementos[0].is_displayed():
                                password_input = elementos[0]
                                logger.info(f"Campo de contraseña encontrado con XPath: {xpath}")
                                break
                        except:
                            pass
                
                # Si encontramos el campo, ingresar la contraseña
                if password_input:
                    password_input.clear()
                    password_input.send_keys(PASSWORD)
                    logger.info("Contraseña ingresada")
                else:
                    logger.error("No se pudo encontrar el campo de contraseña")
                    driver.save_screenshot(f"error_no_campo_password_{intento}.png")
                    driver.quit()
                    continue  # Intentar de nuevo
                
                # 5. Buscar y hacer clic en el botón para enviar el formulario
                logger.info("Buscando botón para enviar formulario...")
                
                submit_button = None
                
                # Método 1: Buscar por texto
                submit_xpaths = [
                    "//button[text()='Siguiente']",
                    "//button[contains(., 'Siguiente')]",
                    "//button[text()='Ingresar']",
                    "//button[contains(., 'Ingresar')]",
                    "//button[text()='Iniciar Sesión']",
                    "//button[contains(., 'Iniciar Sesión')]",
                    "//button[text()='Entrar']",
                    "//button[contains(., 'Entrar')]"
                ]
                
                for xpath in submit_xpaths:
                    elementos = driver.find_elements(By.XPATH, xpath)
                    if elementos and elementos[0].is_displayed():
                        submit_button = elementos[0]
                        logger.info(f"Botón de envío encontrado con XPath: {xpath}")
                        break
                
                # Método 2: Buscar por selector CSS
                if not submit_button:
                    submit_selectors = [
                        "button[type='submit']",
                        ".btn-primary",
                        ".btn-login",
                        ".login-button",
                        ".submit-button",
                        "form input[type='submit']"
                    ]
                    
                    for selector in submit_selectors:
                        elementos = driver.find_elements(By.CSS_SELECTOR, selector)
                        if elementos and elementos[0].is_displayed():
                            submit_button = elementos[0]
                            logger.info(f"Botón de envío encontrado con selector: {selector}")
                            break
                
                # Método 3: Usar el formulario para enviar automáticamente
                if not submit_button:
                    try:
                        # Intentar enviar el formulario directamente presionando Enter
                        password_input.send_keys(Keys.RETURN)
                        logger.info("Formulario enviado presionando Enter en el campo de contraseña")
                        time.sleep(5)
                    except:
                        logger.warning("No se pudo enviar el formulario con Enter")
                        
                        # Intentar buscar el formulario y enviarlo directamente
                        try:
                            form = driver.find_element(By.TAG_NAME, "form")
                            driver.execute_script("arguments[0].submit();", form)
                            logger.info("Formulario enviado con JavaScript")
                            time.sleep(5)
                        except:
                            logger.warning("No se pudo encontrar o enviar el formulario")
                else:
                    # Si encontramos el botón, hacer clic
                    try:
                        # Intentar con clic normal
                        submit_button.click()
                        logger.info("Clic en botón de envío realizado")
                    except:
                        # Si falla, intentar con JavaScript
                        try:
                            driver.execute_script("arguments[0].click();", submit_button)
                            logger.info("Clic en botón de envío realizado con JavaScript")
                        except Exception as e:
                            logger.error(f"Error al hacer clic en botón de envío: {e}")
                            driver.save_screenshot(f"error_no_boton_submit_{intento}.png")
                            driver.quit()
                            continue  # Intentar de nuevo
                
                # Esperar a que se procese el login
                time.sleep(5)
                
                # Tomar captura después del login
                driver.save_screenshot(f"after_login_submission_{intento}.png")
                
                # 6. Verificar si el login fue exitoso
                current_url = driver.current_url
                logger.info(f"URL después de login: {current_url}")
                
                # Guardar HTML para análisis
                with open(f"login_page_{intento}.html", "w", encoding="utf-8") as f:
                    f.write(driver.page_source)
                
                # Buscar indicadores de login exitoso
                success_indicators = [
                    "mi cuenta" in driver.page_source.lower(),
                    "cerrar sesión" in driver.page_source.lower(),
                    "logout" in driver.page_source.lower(),
                    "mi perfil" in driver.page_source.lower(),
                    "bienvenido" in driver.page_source.lower(),
                    "captura de pedidos" in driver.page_source.lower(),
                    "carrito" in driver.page_source.lower(),
                    bool(driver.find_elements(By.CSS_SELECTOR, ".user-profile, .logout-button, a[href*='logout'], .welcome-user, .user-menu"))
                ]
                
                # Determinar si el login fue exitoso
                login_exitoso = any(success_indicators)
                
                if login_exitoso:
                    logger.info("¡LOGIN EXITOSO EN DIFARMER!")
                    return driver
                else:
                    logger.error(f"ERROR: Login en Difarmer fallido (intento {intento}/{max_intentos})")
                    driver.save_screenshot(f"error_login_fallido_{intento}.png")
                    driver.quit()
                    continue  # Intentar de nuevo
                
            except Exception as e:
                logger.error(f"Error durante el proceso de login: {e}")
                driver.save_screenshot(f"error_general_login_{intento}.png")
                driver.quit()
                continue  # Intentar de nuevo
                
        except Exception as e:
            logger.error(f"Error inesperado: {e}")
            if driver:
                driver.quit()
            continue  # Intentar de nuevo
    
    # Si llegamos aquí, es que todos los intentos fallaron
    logger.error(f"ERROR: Login en Difarmer fallido después de {max_intentos} intentos")
    return None
