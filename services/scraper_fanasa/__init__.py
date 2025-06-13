"""
Paquete scraper_fanasa para SOPRIM BOT.
Contiene funcionalidades para extraer información de productos desde FANASA.
"""

# Importar las funciones principales para uso directo
from .main import buscar_info_medicamento, login_fanasa_carrito, buscar_producto, extraer_info_productos

# Exposición de funciones principales para importación directa
__all__ = ['buscar_info_medicamento', 'login_fanasa_carrito', 'buscar_producto', 'extraer_info_productos']
