"""
Módulo de login para Difarmer - Versión mejorada anti-detección
Optimizado para Google Cloud Run con técnicas avanzadas de evasión
"""
import time
import logging
import random
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
import pyautogui  # Para simular movimientos más realistas
pyautogui.FAILSAFE = False

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuración
USERNAME = "C20118"
PASSWORD = "7913"
BASE_URL = "https://www.difarmer.com"
LOGIN_TIMEOUT_SECONDS = 120      # Aumentado para dar más tiempo
MAX_LOGIN_ATTEMPTS = 3
VALIDATION_BUTTON_TIMEOUT = 60   # Aumentado

def random_delay(min_seconds=0.5, max_seconds=2.0):
    """Genera delays aleatorios para simular comportamiento humano"""
    time.sleep(random.uniform(min_seconds, max_seconds))

def move_mouse_naturally(driver, element):
    """Simula movimientos naturales del mouse hacia un elemento"""
    try:
        actions = ActionChains(driver)
        # Movimiento con curvas bezier para parecer más humano
        actions.move_to_element_with_offset(element, 5, 5)
        actions.pause(random.uniform(0.1, 0.3))
        actions.move_to_element(element)
        actions.perform()
        random_delay(0.1, 0.3)
    except:
        pass

def type_like_human(element, text):
    """Escribe texto con velocidad variable como un humano"""
    element.clear()
    for char in text:
        element.send_keys(char)
        time.sleep(random.uniform(0.05, 0.15))  # Velocidad variable entre caracteres

def inicializar_navegador(headless=True):
    """
    Inicializa el navegador con configuración anti-detección mejorada
    """
    options = uc.ChromeOptions()
    
    # Configuración específica para Cloud Run
    if headless:
        # Usar el nuevo modo headless que es menos detectable
        options.add_argument("--headless=new")
        # Configuración esencial para Cloud Run
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        # Desactivar características que delatan automatización
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
    
    # User agent actualizado y más realista
    user_agents = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    ]
    options.add_argument(f'user-agent={random.choice(user_agents)}')
    
    # Configuración adicional para parecer más real
    options.add_argument('--lang=es-ES,es;q=0.9')
    options.add_argument(f"--window-size={random.randint(1366, 1920)},{random.randint(768, 1080)}")
    options.add_argument("--disable-notifications")
    options.add_argument("--disable-popup-blocking")
    
    # Preferencias para evitar detección
    prefs = {
        "credentials_enable_service": False,
        "profile.password_manager_enabled": False,
        "webrtc.ip_handling_policy": "disable_non_proxied_udp",
        "webrtc.multiple_routes_enabled": False,
        "webrtc.nonproxied_udp_enabled": False
    }
    options.add_experimental_option("prefs", prefs)
    
    # Agregar extensiones ficticias para parecer navegador real
    options.add_argument('--load-extension=' + ','.join([
        '/tmp/fake_extension_1',
        '/tmp/fake_extension_2'
    ]))
    
    try:
        logger.info("===== Inicializando navegador con protección anti-detección avanzada =====")
        # Versión específica de Chrome si es necesario
        driver = uc.Chrome(options=options, version_main=120)
        
        # Inyectar JavaScript para ocultar propiedades de automatización
        stealth_js = """
        Object.defineProperty(navigator, 'webdriver', {
            get: () => undefined
        });
        
        Object.defineProperty(navigator, 'plugins', {
            get: () => [1, 2, 3, 4, 5]
        });
        
        Object.defineProperty(navigator, 'languages', {
            get: () => ['es-ES', 'es', 'en']
        });
        
        window.chrome = {
            runtime: {},
            loadTimes: function() {},
            csi: function() {},
            app: {}
        };
        
        Object.defineProperty(navigator, 'permissions', {
            get: () => ({
                query: () => Promise.resolve({ state: 'granted' })
            })
        });
        """
        driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
            'source': stealth_js
        })
        
        # Configurar viewport para evitar detección
        driver.execute_cdp_cmd('Emulation.setDeviceMetricsOverride', {
            'width': random.randint(1366, 1920),
            'height': random.randint(768, 1080),
            'deviceScaleFactor': 1,
            'mobile': False
        })
        
        logger.info("Navegador inicializado con todas las protecciones activadas")
        return driver
        
    except Exception as e:
        logger.error(f"Error al inicializar el navegador: {e}")
        return None

def wait_for_validation_button(driver, timeout=60):
    """
    Espera inteligente para el botón de validación con verificaciones adicionales
    """
    logger.info("Esperando a que se complete la validación de identidad...")
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        try:
            # Buscar el botón en sus diferentes estados
            buttons = driver.find_elements(By.XPATH, 
                "//button[contains(@class, 'btn') and (contains(., 'Validando') or contains(., 'Siguiente'))]"
            )
            
            for button in buttons:
                button_text = button.text.strip()
                button_class = button.get_attribute('class')
                
                # Verificar si el botón está habilitado y tiene el texto correcto
                if 'Siguiente' in button_text and 'disabled' not in button_class:
                    logger.info(f"✅ Botón habilitado detectado: '{button_text}'")
                    # Simular comportamiento humano antes de hacer clic
                    move_mouse_naturally(driver, button)
                    random_delay(0.5, 1.0)
                    return button
                elif 'Validando' in button_text:
                    logger.debug(f"Botón aún validando: '{button_text}'")
            
            # Pequeña pausa antes de verificar nuevamente
            time.sleep(0.5)
            
        except Exception as e:
            logger.debug(f"Error durante la espera: {e}")
    
    raise TimeoutException(f"Timeout esperando el botón de validación después de {timeout} segundos")

def login_difarmer(headless=True):
    """
    Realiza el proceso de login con comportamiento más humano
    """
    for intento in range(1, MAX_LOGIN_ATTEMPTS + 1):
        logger.info(f"🚀 Intento de login #{intento}/{MAX_LOGIN_ATTEMPTS}")
        driver = None
        
        try:
            driver = inicializar_navegador(headless=headless)
            if not driver:
                continue
            
            # Navegar a la página con delay aleatorio
            logger.info("Navegando a Difarmer...")
            driver.get(BASE_URL)
            random_delay(2, 4)  # Espera más natural
            
            # Simular scroll aleatorio como usuario real
            driver.execute_script(f"window.scrollTo(0, {random.randint(100, 300)});")
            random_delay(0.5, 1)
            driver.execute_script("window.scrollTo(0, 0);")
            
            # Buscar y hacer clic en el botón de login
            logger.info("Buscando botón 'Iniciar Sesion'...")
            login_button = WebDriverWait(driver, 20).until(
                EC.element_to_be_clickable((By.XPATH, 
                    "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'iniciar ses')]"
                ))
            )
            
            # Mover mouse naturalmente y hacer clic
            move_mouse_naturally(driver, login_button)
            login_button.click()
            random_delay(1, 2)
            
            # Esperar a que aparezcan los campos de login
            logger.info("Esperando formulario de login...")
            usuario_input = WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 
                    "input[placeholder*='Usuario'], input[name*='user'], input[id*='user']"
                ))
            )
            
            # Ingresar credenciales con comportamiento humano
            logger.info("Ingresando credenciales...")
            move_mouse_naturally(driver, usuario_input)
            usuario_input.click()
            random_delay(0.3, 0.7)
            type_like_human(usuario_input, USERNAME)
            
            # Buscar campo de contraseña
            password_input = driver.find_element(By.CSS_SELECTOR, "input[type='password']")
            move_mouse_naturally(driver, password_input)
            password_input.click()
            random_delay(0.3, 0.7)
            type_like_human(password_input, PASSWORD)
            
            # Esperar un momento antes de buscar el botón
            random_delay(1, 2)
            
            # Esperar a que el botón de validación esté listo
            siguiente_button = wait_for_validation_button(driver, VALIDATION_BUTTON_TIMEOUT)
            
            # Hacer clic con comportamiento natural
            driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", siguiente_button)
            random_delay(0.5, 1)
            siguiente_button.click()
            
            # Esperar respuesta del servidor
            logger.info("Esperando respuesta del login...")
            random_delay(5, 8)
            
            # Verificar éxito del login
            success_indicators = [
                "mi cuenta", "cerrar sesión", "logout", "mi perfil",
                "bienvenido", "captura de pedidos", "carrito"
            ]
            
            page_text = driver.page_source.lower()
            if any(indicator in page_text for indicator in success_indicators):
                logger.info("🎉 ¡LOGIN EXITOSO!")
                # Pequeña navegación adicional para confirmar
                random_delay(1, 2)
                return driver
            else:
                raise Exception("No se detectaron indicadores de login exitoso")
                
        except Exception as e:
            logger.error(f"❌ Error en intento #{intento}: {str(e)}")
            if driver:
                # Guardar screenshot para debugging
                try:
                    driver.save_screenshot(f"error_login_intento_{intento}.png")
                    with open(f"page_source_intento_{intento}.html", "w") as f:
                        f.write(driver.page_source)
                except:
                    pass
                driver.quit()
            
            if intento < MAX_LOGIN_ATTEMPTS:
                wait_time = random.uniform(5, 10)
                logger.info(f"Esperando {wait_time:.1f} segundos antes del siguiente intento...")
                time.sleep(wait_time)
    
    logger.error("🚫 Login fallido después de todos los intentos")
    return None

# Función auxiliar para testing
def test_login():
    """Función de prueba para verificar el login"""
    # Primero probar en modo visible para debugging
    logger.info("=== PRUEBA EN MODO VISIBLE ===")
    driver = login_difarmer(headless=False)
    if driver:
        logger.info("✅ Login exitoso en modo visible")
        driver.quit()
    
    # Luego probar en modo headless
    logger.info("\n=== PRUEBA EN MODO HEADLESS ===")
    driver = login_difarmer(headless=True)
    if driver:
        logger.info("✅ Login exitoso en modo headless")
        driver.quit()

if __name__ == "__main__":
    test_login()
