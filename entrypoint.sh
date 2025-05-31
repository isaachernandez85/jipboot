#!/bin/bash
set -e

echo "Iniciando SOPRIM BOT con soporte para múltiples scrapers..."

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

echo "Comprobando instalación de Chrome..."
# Verificar instalación de Chrome
if ! command -v google-chrome &> /dev/null; then
    echo "ADVERTENCIA: Google Chrome no está instalado. Los scrapers podrían no funcionar correctamente."
else
    chrome_version=$(google-chrome --version)
    echo "Chrome instalado: $chrome_version"
fi

echo "Directorio actual: $(pwd)"
ls -la

if [ ! -f "main.py" ]; then
    echo "ERROR: No se encuentra main.py"
    exit 1
fi

export PORT=${PORT:-8080}
echo "Puerto configurado: $PORT"

echo "Arrancando servidor uvicorn..."
exec uvicorn main:app --host 0.0.0.0 --port $PORT