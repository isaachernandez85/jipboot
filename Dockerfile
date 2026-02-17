FROM python:3.10-slim
# Variables de entorno para Python
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1
# Instalar dependencias del sistema
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    unzip \
    fonts-liberation \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libatspi2.0-0 \
    libcups2 \
    libdbus-1-3 \
    libdrm2 \
    libgbm1 \
    libgtk-3-0 \
    libnspr4 \
    libnss3 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxkbcommon0 \
    libxrandr2 \
    xdg-utils \
    xvfb \
    x11vnc \
    fluxbox \
    libxi6 \
    libxss1 \
    libappindicator3-1 \
    libxtst6 \
    libnss3-dev \
    procps \
    curl \
    locales \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*
# Configurar locales
RUN sed -i '/es_MX.UTF-8/s/^# //g' /etc/locale.gen && \
    locale-gen
ENV LANG=es_MX.UTF-8 \
    LANGUAGE=es_MX:es \
    LC_ALL=es_MX.UTF-8
# Descargar e instalar Google Chrome (método actualizado sin apt-key)
RUN wget -q -O /tmp/google-chrome-key.pub https://dl-ssl.google.com/linux/linux_signing_key.pub \
    && gpg --dearmor -o /usr/share/keyrings/google-chrome.gpg /tmp/google-chrome-key.pub \
    && echo "deb [arch=amd64 signed-by=/usr/share/keyrings/google-chrome.gpg] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list \
    && apt-get update \
    && apt-get install -y google-chrome-stable \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* /tmp/google-chrome-key.pub
# Verificar instalación de Chrome
RUN google-chrome --version
# Crear directorio de trabajo
WORKDIR /app
# Crear directorios para logs y capturas de pantalla de todos los scrapers
RUN mkdir -p /app/debug_screenshots /app/debug_logs /app/conversations \
    /app/.cache /app/.config /app/downloads
# Configurar permisos para Chrome
RUN chmod -R 755 /app
# Copiar requirements y instalar dependencias
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# Instalar undetected-chromedriver con versión específica
RUN pip install --no-cache-dir undetected-chromedriver==3.5.4
# Instalar dependencias adicionales para mejor debugging
RUN pip install --no-cache-dir \
    psutil \
    python-dotenv
# Copiar código de la aplicación
COPY . .
# Dar permisos al entrypoint
RUN chmod +x entrypoint.sh
# Variables de entorno para Chrome
ENV DISPLAY=:99 \
    CHROME_BIN=/usr/bin/google-chrome-stable \
    CHROME_PATH=/usr/bin/google-chrome-stable \
    PORT=8080
# Exponer puerto
EXPOSE $PORT
# Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:$PORT/health || exit 1
# Definir el punto de entrada
ENTRYPOINT ["./entrypoint.sh"]
