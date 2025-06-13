#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import time
import re
from selenium.webdriver.common.by import By

from .settings import logger

def extraer_info_producto(driver):
    """
    Extrae información detallada del producto de la página actual.
   
    Args:
        driver (webdriver.Chrome): Instancia del navegador con la página de detalle abierta
       
    Returns:
        dict: Diccionario con la información del producto o None si hay error
    """
    if not driver:
        logger.error("No se proporcionó un navegador válido")
        return None
   
    try:
        # Esperar a que cargue la página de detalle
        time.sleep(5)
       
        # Tomar captura de la página de detalle
        driver.save_screenshot("detalle_producto.png")
       
        # Guardar HTML para análisis
        with open("detalle_producto.html", "w", encoding="utf-8") as f:
            f.write(driver.page_source)
        logger.info("HTML de detalle guardado para análisis")
       
        # Inicializar diccionario para almacenar la información
        info_producto = {
            'nombre': None,
            'laboratorio': None,
            'codigo_barras': None,
            'registro_sanitario': None,
            'codigo_sat': None,
            'codigo_difarmer': None,
            'precio_publico': None,
            'mi_precio': None,  # Campo específico para Mi precio
            'principio_activo': None,
            'existencia': None,
            'url': driver.current_url,
            'imagen': None
        }
        
        # MÉTODO SIMPLE: Capturar todo el texto de la página y extraer datos con regex
        texto_completo = driver.find_element(By.TAG_NAME, "body").text
        
        # Extraer nombre del producto - primera línea en mayúsculas después del título
        h1_elements = driver.find_elements(By.TAG_NAME, "h1")
        for h1 in h1_elements:
            if h1.text and len(h1.text) > 5:
                info_producto['nombre'] = h1.text.strip()
                logger.info(f"Nombre extraído de h1: {info_producto['nombre']}")
                break
        
        # Si no encontramos en h1, buscar en el texto
        if not info_producto['nombre']:
            # Buscar líneas que parezcan nombre de medicamento (mayúsculas, MG, TABS)
            lines = texto_completo.split('\n')
            for line in lines:
                if re.search(r'[A-Z]{3,}.*(?:MG|TABS|TAB)', line):
                    info_producto['nombre'] = line.strip()
                    logger.info(f"Nombre extraído del texto: {info_producto['nombre']}")
                    break
        
        # Extraer laboratorio
        match = re.search(r'Laboratorio:\s*([^\n]+)', texto_completo)
        if match:
            info_producto['laboratorio'] = match.group(1).strip()
        
        # Extraer código de barras
        match = re.search(r'Código de barras:\s*([^\n]+)', texto_completo)
        if match:
            info_producto['codigo_barras'] = match.group(1).strip()
        
        # Extraer registro sanitario
        match = re.search(r'Registro S\.S\.A\.:\s*([^\n]+)', texto_completo)
        if match:
            info_producto['registro_sanitario'] = match.group(1).strip()
        
        # Extraer código SAT
        match = re.search(r'Código SAT:\s*([^\n]+)', texto_completo)
        if match:
            info_producto['codigo_sat'] = match.group(1).strip()
        
        # Extraer código Difarmer
        match = re.search(r'Código Difarmer:\s*([^\n]+)', texto_completo)
        if match:
            info_producto['codigo_difarmer'] = match.group(1).strip()
        
        # Extraer precio público
        match = re.search(r'Precio Público:\s*\$?([0-9.,]+)', texto_completo)
        if match:
            info_producto['precio_publico'] = match.group(1).strip()
        
        # CRÍTICO: Extraer Mi precio
        # Método 1: Buscar texto exacto "Mi precio:"
        match = re.search(r'Mi precio:\s*\$?([0-9.,]+)', texto_completo)
        if match:
            info_producto['mi_precio'] = match.group(1).strip()
            logger.info(f"Mi precio extraído: {info_producto['mi_precio']}")
        
        # Método 2: Buscar específicamente elementos con "Mi precio:"
        if not info_producto['mi_precio']:
            try:
                mi_precio_elements = driver.find_elements(By.XPATH, "//*[contains(text(), 'Mi precio:')]")
                for elem in mi_precio_elements:
                    if "Mi precio:" in elem.text:
                        match = re.search(r'Mi precio:\s*\$?([0-9.,]+)', elem.text)
                        if match:
                            info_producto['mi_precio'] = match.group(1).strip()
                            logger.info(f"Mi precio extraído de elemento: {info_producto['mi_precio']}")
                            break
            except:
                pass
        
        # Método 3: Buscar todos los elementos que contengan "$"
        if not info_producto['mi_precio']:
            try:
                elementos_precio = driver.find_elements(By.XPATH, "//*[contains(text(), '$')]")
                for elem in elementos_precio:
                    texto = elem.text.strip()
                    if "Mi precio:" in texto:
                        match = re.search(r'\$([0-9.,]+)', texto)
                        if match:
                            info_producto['mi_precio'] = match.group(1).strip()
                            logger.info(f"Mi precio extraído de elemento con $: {info_producto['mi_precio']}")
                            break
            except:
                pass
        
        # CRÍTICO: Extraer existencia en León
        match = re.search(r'León:\s*([0-9,]+)', texto_completo)
        if match:
            info_producto['existencia'] = match.group(1).strip()
            logger.info(f"Existencia extraída: {info_producto['existencia']}")
        
        # Si no se encontró con regex, buscar elementos específicos
        if not info_producto['existencia']:
            try:
                leon_elements = driver.find_elements(By.XPATH, "//*[contains(text(), 'León:')]")
                for elem in leon_elements:
                    texto = elem.text
                    match = re.search(r'León:\s*([0-9,]+)', texto)
                    if match:
                        info_producto['existencia'] = match.group(1).strip()
                        logger.info(f"Existencia extraída de elemento: {info_producto['existencia']}")
                        break
            except:
                pass
        
        # Extraer imagen del producto
        imgs = driver.find_elements(By.TAG_NAME, "img")
        for img in imgs:
            src = img.get_attribute("src")
            if src and not src.endswith(('.ico', '.svg')) and not 'logo' in src.lower():
                info_producto['imagen'] = src
                break
        
        # Si aún no tenemos nombre, usar ID de la URL
        if not info_producto['nombre']:
            url_match = re.search(r'/(\d+)$', info_producto['url'])
            if url_match:
                info_producto['nombre'] = f"Producto ID: {url_match.group(1)}"
                logger.info(f"Nombre extraído de URL: {info_producto['nombre']}")
        
        # Imprimir el texto completo a un archivo para diagnóstico
        with open("texto_completo.txt", "w", encoding="utf-8") as f:
            f.write(texto_completo)
        logger.info("Texto completo guardado para diagnóstico")
        
        # NUEVO: Imprimir los valores obtenidos al log para diagnóstico
        logger.info("==== DATOS EXTRAÍDOS ====")
        for campo, valor in info_producto.items():
            logger.info(f"{campo}: {valor}")
        logger.info("=======================")
        
        return info_producto
        
    except Exception as e:
        logger.error(f"Error durante la extracción de información del producto: {e}")
        driver.save_screenshot("error_extraccion.png")
        return {
            'nombre': f"Error: {str(e)}",
            'laboratorio': "Error",
            'codigo_barras': "Error",
            'registro_sanitario': "Error",
            'codigo_sat': "Error",
            'codigo_difarmer': "Error",
            'precio_publico': "Error",
            'mi_precio': "Error",
            'principio_activo': "Error",
            'existencia': "Error",
            'url': driver.current_url if driver else "No disponible",
            'imagen': None
        }
