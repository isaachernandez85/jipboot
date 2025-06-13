#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from .login import login_difarmer
from .search import buscar_producto
from .extract import extraer_info_producto
from .save import guardar_resultados
from .settings import logger

def normalizar_busqueda_difarmer(producto_nombre):
    """
    Normalización para DIFARMER: Mantener formato original.
    Difarmer funciona excelente con el formato completo.
    Solo se hacen ajustes menores de limpieza.
    
    Args:
        producto_nombre (str): Nombre completo del producto
        
    Returns:
        str: Producto optimizado para Difarmer (formato completo)
    """
    if not producto_nombre:
        return producto_nombre
    
    # Difarmer funciona mejor con formato completo, solo limpieza básica
    texto = producto_nombre.strip()
    
    # Pequeñas optimizaciones que mejoran la búsqueda en Difarmer
    optimizaciones = {
        # Estandarizar unidades comunes
        ' mgs ': ' mg ',
        ' Mgs ': ' mg ',
        ' MGS ': ' mg ',
        ' mls ': ' ml ',
        ' Mls ': ' ml ',
        ' MLS ': ' ml ',
        # Estandarizar formas farmacéuticas
        ' tableta ': ' tabletas ',
        ' capsula ': ' cápsulas ',
        ' ampolla ': ' ampolletas ',
        # Eliminar espacios múltiples
        '  ': ' ',
        '   ': ' '
    }
    
    for original, reemplazo in optimizaciones.items():
        texto = texto.replace(original, reemplazo)
    
    # Eliminar espacios al inicio y final
    resultado = texto.strip()
    
    logger.info(f"[DIFARMER] Optimización: '{producto_nombre}' → '{resultado}'")
    return resultado

def buscar_info_medicamento(nombre_medicamento, headless=True):
    """
    Función principal que busca información de un medicamento en Difarmer.
    ACTUALIZADO: Con normalización específica para Difarmer.
   
    Args:
        nombre_medicamento (str): Nombre del medicamento a buscar
        headless (bool): Si es True, el navegador se ejecuta en modo headless
       
    Returns:
        dict: Diccionario con la información del medicamento o None si no se encuentra
    """
    driver = None
    try:
        # ✅ NUEVO: Optimizar búsqueda para Difarmer (mantiene formato completo)
        nombre_optimizado = normalizar_busqueda_difarmer(nombre_medicamento)
        
        # 1. Iniciar sesión en Difarmer
        logger.info(f"Iniciando proceso para buscar información sobre: '{nombre_optimizado}'")
       
        driver = login_difarmer(headless=headless)
        if not driver:
            logger.error("No se pudo iniciar sesión en Difarmer. Abortando búsqueda.")
            return None
       
        # 2. Buscar el producto con nombre optimizado
        logger.info(f"Sesión iniciada. Buscando producto: '{nombre_optimizado}'")
       
        resultado_busqueda = buscar_producto(driver, nombre_optimizado)
       
        if not resultado_busqueda:
            logger.warning(f"No se pudo encontrar o acceder al producto: '{nombre_optimizado}'")
            return None
       
        # 3. Extraer información del producto
        logger.info("Extrayendo información del producto...")
        info_producto = extraer_info_producto(driver)
        
        # Verificar que info_producto sea un diccionario o None
        if info_producto is not None and not isinstance(info_producto, dict):
            logger.error(f"Error: extraer_info_producto no devolvió un diccionario, devolvió {type(info_producto)}")
            return None
        
        return info_producto
       
    except Exception as e:
        logger.error(f"Error general durante el proceso: {e}")
        return None
    finally:
        if driver:
            logger.info("Cerrando navegador...")
            driver.quit()

# Función principal para ejecutar desde línea de comandos
if __name__ == "__main__":
    import sys
   
    print("=== Sistema de Búsqueda de Medicamentos en Difarmer ===")
   
    # Si se proporciona un argumento por línea de comandos, usarlo como nombre del medicamento
    if len(sys.argv) > 1:
        medicamento = " ".join(sys.argv[1:])
    else:
        # De lo contrario, pedir al usuario
        medicamento = input("Ingrese el nombre del medicamento a buscar: ")
   
    # ✅ NUEVO: Mostrar optimización
    medicamento_optimizado = normalizar_busqueda_difarmer(medicamento)
    print(f"\n=== OPTIMIZACIÓN DIFARMER ===")
    print(f"Original: {medicamento}")
    print(f"Optimizado: {medicamento_optimizado}")
    print("=" * 40)
    
    print(f"\nBuscando información sobre: {medicamento_optimizado}")
    print("Espere un momento...\n")
   
    # Definir el modo headless basado en entorno
    import os
    # Si estamos en un entorno de servidor o container, usar headless=True, de lo contrario False para desarrollo
    headless = os.environ.get('ENVIRONMENT', 'production').lower() != 'development'
    
    # Buscar información del medicamento
    info = buscar_info_medicamento(medicamento, headless=headless)
   
    if info:
        # Guardar la información en un archivo JSON
        guardar_resultados(info)
        
        # ✅ NUEVO: Mostrar información mejorada en consola
        print("\n=== INFORMACIÓN DEL PRODUCTO ===")
        print(f"Nombre: {info.get('nombre', 'No disponible')}")
        print(f"Laboratorio: {info.get('laboratorio', 'No disponible')}")
        print(f"Mi Precio: {info.get('mi_precio', 'No disponible')}")
        print(f"Precio Público: {info.get('precio_publico', 'No disponible')}")
        print(f"Existencia León: {info.get('existencia', 'No disponible')}")
        print(f"Código Difarmer: {info.get('codigo_difarmer', 'No disponible')}")
        print(f"Código de Barras: {info.get('codigo_barras', 'No disponible')}")
        print(f"Registro Sanitario: {info.get('registro_sanitario', 'No disponible')}")
        print(f"URL: {info.get('url', 'No disponible')}")
        if info.get('imagen'):
            print(f"Imagen: {info.get('imagen')}")
    else:
        print("No se pudo encontrar información sobre el medicamento solicitado")
