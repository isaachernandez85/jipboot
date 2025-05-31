#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import os

# Configuración de credenciales - usar variables de entorno o valores por defecto
USERNAME = os.environ.get('DIFARMER_USERNAME', 'C20118')  # Usuario para Difarmer
PASSWORD = os.environ.get('DIFARMER_PASSWORD', '7913')    # Contraseña para Difarmer
BASE_URL = os.environ.get('DIFARMER_BASE_URL', 'https://www.difarmer.com')  # URL base del sitio
TIMEOUT = int(os.environ.get('DIFARMER_TIMEOUT', '15'))   # Tiempo máximo de espera para elementos (segundos)

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
