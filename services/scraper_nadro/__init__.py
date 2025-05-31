"""
Paquete scraper_nadro para SOPRIM BOT.
Contiene funcionalidades para extraer información de productos desde NADRO.
"""

# Importar las funciones principales para uso directo
from .main import buscar_info_medicamento

# Exposición de funciones principales para importación directa
__all__ = ['buscar_info_medicamento']