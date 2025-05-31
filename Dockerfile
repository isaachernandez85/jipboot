FROM python:3.10-slim

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
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Descargar e instalar Google Chrome
RUN wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add - \
    && echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google.list \
    && apt-get update \
    && apt-get install -y google-chrome-stable \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Crear directorio de trabajo
WORKDIR /app

# Crear directorios para logs y capturas de pantalla de todos los scrapers
RUN mkdir -p /app/debug_screenshots /app/debug_logs /app/conversations

# Copiar requirements y instalar dependencias
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Agregar undetected-chromedriver para el scraper NADRO
# (Compatible con los demás scrapers, solo añade una dependencia nueva)
RUN pip install --no-cache-dir undetected-chromedriver==3.5.4

# Copiar código de la aplicación
COPY . .

# Dar permisos al entrypoint
RUN chmod +x entrypoint.sh

# Exponer puerto
ENV PORT=8080
EXPOSE $PORT

# Definir el punto de entrada
ENTRYPOINT ["./entrypoint.sh"]