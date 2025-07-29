"""
Módulo de login para Difarmer, versión final y robusta.
- Conserva la lógica original de selectores múltiples y opciones de navegador.
- Utiliza undetected-chromedriver para evitar la detección de bots.
- Implementa espera explícita para el nuevo botón de validación de identidad.
- Optimizado para entornos de Cloud Run (headless).
"""
import time
import logging
# ✅ CAMBIOS: Importaciones actualizadas para la solución
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Configurar logging (se mantiene tu configuración original)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuración (se mantiene tu configuración original)
USERNAME = "C20118"
PASSWORD = "7913"
BASE_URL = "https://www.difarmer.com"
LOGIN_TIMEOUT_SECONDS = 90      # Timeout global para cada intento
MAX_LOGIN_ATTEMPTS = 3          # Número de reintentos
VALIDATION_BUTTON_TIMEOUT = 45  # Tiempo máximo para esperar el botón "Validando..."

def inicializar_navegador(headless=True):
    """
    ✅ FUNCIÓN MEJORADA: Inicializa el navegador con una configuración headless simplificada para el servidor.
    """
    options = uc.ChromeOptions()
    
    # ✅ CAMBIO APLICADO: Simplificamos el bloque headless para probar un perfil más limpio.
    if headless:
        # Dejamos solo las opciones más importantes y probadas para entornos de servidor.
        # Un perfil más simple puede ser menos sospechoso.
        options.add_argument("--headless=new")
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-gpu')
        options.add_argument('--disable-dev-shm-usage')
    
    # Se mantienen el resto de tus opciones de configuración para robustez
    options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36')
    options.add_argument('--lang=es-ES')
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-notifications")
    options.add_argument("--disable-popup-blocking")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-setuid-sandbox")
    options.add_argument("--remote-debugging-port=9222")
    options.add_argument("--no-first-run")
    options.add_argument("--no-default-browser-check")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--disable-infobars")
    options.add_argument("--disable-browser-side-navigation")
    options.add_argument("--dns-prefetch-disable")
    options.add_argument("--log-level=1")
    options.add_argument("--disable-software-rasterizer")
    
    try:
        logger.info("===== Inicializando con Undetected Chromedriver (Configuración Simplificada para Servidor) =====")
        # Pasamos headless=True para que uc.Chrome sepa el modo, pero las opciones ya están configuradas.
        driver = uc.Chrome(options=options, headless=headless)
        logger.info("Navegador (undetected) inicializado correctamente.")
        return driver
    except Exception as e:
        logger.error(f"Error al inicializar el navegador (undetected): {e}")
        return None

def login_difarmer(headless=True):
    """
    Realiza el proceso de login conservando tu lógica de búsqueda de elementos,
    pero adaptada para el nuevo botón de validación.
    """
    for intento in range(1, MAX_LOGIN_ATTEMPTS + 1):
        logger.info(f"🚀 Iniciando intento de login #{intento}/{MAX_LOGIN_ATTEMPTS}")
        start_time = time.time()
        driver = None
        
        try:
            driver = inicializar_navegador(headless=headless)
            if not driver:
                logger.error("No se pudo inicializar el navegador. Reintentando...")
                continue

            driver.get(BASE_URL)
            time.sleep(3)

            logger.info("Buscando botón 'Iniciar Sesion'...")
            login_button = None
            xpaths_login = [
                "//button[contains(., 'Iniciar Sesion')]", "//a[contains(., 'Iniciar Sesion')]",
                "//button[contains(., 'Iniciar Sesión')]", "//a[contains(., 'Iniciar Sesión')]",
                "//*[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'iniciar sesion')]"
            ]
            for xpath in xpaths_login:
                elementos = driver.find_elements(By.XPATH, xpath)
                if elementos:
                    login_button = elementos[0]
                    logger.info(f"Botón 'Iniciar Sesion' encontrado con XPath: {xpath}")
                    break
            
            if not login_button:
                css_selectors = [
                    ".btn-primary", ".btn-login", ".login-button", 
                    "button.blue-button", ".difarmer-login-button"
                ]
                for selector in css_selectors:
                    elementos = driver.find_elements(By.CSS_SELECTOR, selector)
                    if elementos:
                        login_button = elementos[0]
                        logger.info(f"Botón 'Iniciar Sesion' encontrado con selector CSS: {selector}")
                        break
            
            if login_button:
                driver.execute_script("arguments[0].click();", login_button)
                logger.info("Clic en 'Iniciar Sesion' realizado con JavaScript.")
                time.sleep(2)
            else:
                raise Exception("No se encontró el botón principal de 'Iniciar Sesion'")

            logger.info("Buscando y rellenando credenciales...")
            usuario_input = None
            username_selectors = [
                "input[placeholder='Usuario']", "input[name='username']", "input[id='user']",
                "input[id='username']", "input[id='email']", "input.username-field"
            ]
            for selector in username_selectors:
                elementos = driver.find_elements(By.CSS_SELECTOR, selector)
                if elementos and elementos[0].is_displayed():
                    usuario_input = elementos[0]
                    logger.info(f"Campo de usuario encontrado con selector: {selector}")
                    break
            
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
                    except: pass
            
            if not usuario_input: raise Exception("No se pudo encontrar el campo de usuario con ninguna estrategia.")
            usuario_input.clear()
            usuario_input.send_keys(USERNAME)
            
            password_input = driver.find_element(By.CSS_SELECTOR, "input[type='password']")
            password_input.clear()
            password_input.send_keys(PASSWORD)
            logger.info("Credenciales ingresadas.")

            # ✅ CAMBIO CLAVE: Ahora esperamos a que el texto "Siguiente" aparezca en el botón.
            logger.info(f"Esperando hasta {VALIDATION_BUTTON_TIMEOUT}s a que el botón cambie a 'Siguiente'...")
            validation_button_xpath = "//button[contains(., 'Validando identidad...') or contains(., 'Siguiente')]"
            
            wait = WebDriverWait(driver, VALIDATION_BUTTON_TIMEOUT)
            
            # Esta es la nueva condición, mucho más precisa.
            wait.until(
                EC.text_to_be_present_in_element((By.XPATH, validation_button_xpath), 'Siguiente')
            )
            
            # Una vez que el texto aparece, encontramos el botón y hacemos clic.
            siguiente_button = driver.find_element(By.XPATH, validation_button_xpath)
            logger.info("✅ Botón 'Siguiente' encontrado. Procediendo con el clic.")
            siguiente_button.click()
            time.sleep(7)

            logger.info("Verificando el resultado del login...")
            page_source_lower = driver.page_source.lower()
            success_indicators = [
                "mi cuenta" in page_source_lower, "cerrar sesión" in page_source_lower,
                "logout" in page_source_lower, "mi perfil" in page_source_lower,
                "bienvenido" in page_source_lower, "captura de pedidos" in page_source_lower,
                "carrito" in page_source_lower,
                bool(driver.find_elements(By.CSS_SELECTOR, ".user-profile, .logout-button, a[href*='logout'], .welcome-user, .user-menu"))
            ]
            if any(success_indicators):
                logger.info("🎉 ¡LOGIN EXITOSO EN DIFARMER!")
                return driver
            else:
                raise Exception("Login fallido. No se encontraron indicadores de éxito post-login.")

        except Exception as e:
            logger.error(f"❌ Error en el intento de login #{intento}: {e}")
            if driver:
                driver.save_screenshot(f"error_intento_{intento}.png")
                driver.quit()
            
            if time.time() - start_time > LOGIN_TIMEOUT_SECONDS:
                logger.error("Timeout global alcanzado. Abortando reintentos.")
                break
            
            if intento < MAX_LOGIN_ATTEMPTS:
                logger.info("Esperando 5 segundos antes del siguiente intento...")
                time.sleep(5)

    logger.error(f"🚫 Login en Difarmer fallido después de {MAX_LOGIN_ATTEMPTS} intentos.")
    return None
