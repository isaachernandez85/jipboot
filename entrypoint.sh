#!/bin/bash
set -e

echo "🚀 Iniciando SOPRIM BOT con soporte para múltiples scrapers y anti-detección..."

# Función para limpiar procesos al salir
cleanup() {
    echo "🧹 Limpiando procesos..."
    if [ ! -z "$XVFB_PID" ]; then
        kill -9 $XVFB_PID 2>/dev/null || true
    fi
    # Matar procesos Chrome zombies
    pkill -9 chrome || true
    pkill -9 chromedriver || true
}

# Configurar trap para limpieza
trap cleanup EXIT

# Debug de variables de entorno
if [ -z "$GEMINI_API_KEY" ]; then
    echo "ADVERTENCIA: GEMINI_API_KEY no configurada"
fi
if [ -z "$TWILIO_ACCOUNT_SID" ]; then
    echo "ADVERTENCIA: TWILIO_ACCOUNT_SID no configurada"
fi
if [ -z "$TWILIO_AUTH_TOKEN" ]; then
    echo "ADVERTENCIA: TWILIO_AUTH_TOKEN no configurada"
fi
if [ -z "$TWILIO_WHATSAPP_SANDBOX_NUMBER" ]; then
    echo "ADVERTENCIA: TWILIO_WHATSAPP_SANDBOX_NUMBER no configurada"
fi

# Crear directorios necesarios para los scrapers si no existen
mkdir -p debug_screenshots debug_logs conversations
mkdir -p /tmp/.X11-unix /app/.cache /app/downloads
chmod 1777 /tmp/.X11-unix

# ⭐ CRÍTICO: Iniciar Xvfb (display virtual) para anti-detección
echo "📺 Iniciando display virtual (Xvfb)..."
Xvfb :99 -screen 0 1920x1080x24 -nolisten tcp -nolisten unix &
XVFB_PID=$!
export DISPLAY=:99

# Esperar a que Xvfb esté listo
sleep 3

# Verificar que Xvfb está funcionando
if ! kill -0 $XVFB_PID 2>/dev/null; then
    echo "❌ Error al iniciar Xvfb - esto puede causar problemas con los scrapers"
else
    echo "✅ Display virtual iniciado correctamente en DISPLAY=$DISPLAY"
fi

# ⭐ Configurar el entorno para Chrome con anti-detección
export CHROME_DEVEL_SANDBOX=/usr/local/sbin/chrome-devel-sandbox
export XDG_CONFIG_HOME=/app/.config
export XDG_CACHE_HOME=/app/.cache
export CHROME_BIN=/usr/bin/google-chrome-stable
export CHROME_PATH=/usr/bin/google-chrome-stable

# ⭐ Configuración de zona horaria (importante para algunos scrapers)
export TZ=America/Mexico_City
export LANG=es_MX.UTF-8
export LC_ALL=C.UTF-8

# ⭐ Variables para mejorar la compatibilidad con Chrome headless
export CHROME_ARGS="--no-sandbox --disable-dev-shm-usage --disable-gpu --disable-software-rasterizer"

# Limpiar archivos de sesiones Chrome anteriores
echo "🧹 Limpiando archivos de sesiones anteriores..."
rm -rf /app/.cache/google-chrome
rm -rf /tmp/.com.google.Chrome*
rm -rf /tmp/chrome*
rm -rf /home/*/.config/google-chrome/Singleton*

echo "Comprobando instalación de Chrome..."
# Verificar instalación de Chrome
if ! command -v google-chrome &> /dev/null; then
    echo "❌ ERROR: Google Chrome no está instalado. Los scrapers no funcionarán."
    exit 1
else
    chrome_version=$(google-chrome --version)
    echo "✅ Chrome instalado: $chrome_version"
    
    # Verificar que Chrome puede ejecutarse con las opciones anti-detección
    echo "🔍 Verificando Chrome con opciones headless..."
    timeout 5 google-chrome --headless=new --no-sandbox --disable-gpu --dump-dom https://example.com > /dev/null 2>&1 && \
        echo "✅ Chrome headless funciona correctamente" || \
        echo "⚠️  Chrome headless puede tener problemas"
fi

# Verificar ChromeDriver si está instalado
if command -v chromedriver &> /dev/null; then
    chromedriver_version=$(chromedriver --version 2>/dev/null | head -1)
    echo "✅ ChromeDriver: $chromedriver_version"
fi

echo "📁 Directorio actual: $(pwd)"
echo "📋 Contenido del directorio:"
ls -la

if [ ! -f "main.py" ]; then
    echo "❌ ERROR: No se encuentra main.py"
    exit 1
fi

# Mostrar información del sistema para debugging
echo "📊 Información del sistema:"
echo "- Usuario: $(whoami)"
echo "- Memoria disponible: $(free -h | grep Mem | awk '{print $7}')"
echo "- Procesos Chrome: $(pgrep -c chrome || echo "0")"

export PORT=${PORT:-8080}
echo "🌐 Puerto configurado: $PORT"

# ⭐ Configurar ulimits para manejar múltiples procesos Chrome
ulimit -n 4096
ulimit -u 2048

echo "🎯 Arrancando servidor uvicorn..."
echo "=========================================="

# Ejecutar uvicorn con configuración optimizadaaa
   exec uvicorn main:app \
       --host 0.0.0.0 \
       --port $PORT \
       --workers 1 \
       --loop asyncio \
       --log-level info
