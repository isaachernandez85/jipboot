#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Este archivo inicializa el paquete
# Hace que sea posible importar desde la raíz
# Ejemplo: from scraper_difarmer import buscar_info_medicamento

from .main import buscar_info_medicamento
from .save import guardar_resultados

# Exposición de funciones principales para importación directa
__all__ = ['buscar_info_medicamento', 'guardar_resultados']
