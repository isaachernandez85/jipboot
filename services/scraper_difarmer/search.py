#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import time
import re
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

from .settings import TIMEOUT, logger

def calcular_similitud_producto(busqueda, producto_encontrado):
    """
    Calcula la similitud entre el término de búsqueda y el producto encontrado.
    
    Args:
        busqueda (str): Término buscado por el usuario
        producto_encontrado (str): Nombre del producto encontrado
        
    Returns:
        float: Puntuación de similitud (0.0 a 1.0)
    """
    if not busqueda or not producto_encontrado:
        return 0.0
    
    # Normalizar ambos textos
    busqueda_norm = busqueda.lower().strip()
    producto_norm = producto_encontrado.lower().strip()
    
    # Eliminat artículos y palabras comunes
    palabras_ignorar = ['el', 'la', 'los', 'las', 'un', 'una', 'de', 'del', 'con', 'c/', 'mg', 'ml', 'tabs', 'tab', 'cap']
    
    # Dividir en palabras
    palabras_busqueda = [p for p in busqueda_norm.split() if p not in palabras_ignorar and len(p) > 2]
    palabras_producto = [p for p in producto_norm.split() if p not in palabras_ignorar and len(p) > 2]
    
    if not palabras_busqueda:
        return 0.0
    
    # Contar coincidencias exactas
    coincidencias_exactas = 0
    for palabra_busq in palabras_busqueda:
        if any(palabra_busq in palabra_prod for palabra_prod in palabras_producto):
            coincidencias_exactas += 1
    
    # Calcular puntuación base
    puntuacion_base = coincidencias_exactas / len(palabras_busqueda)
    
    # Bonus por coincidencia al inicio del nombre
    if producto_norm.startswith(busqueda_norm[:min(5, len(busqueda_norm))]):
        puntuacion_base += 0.3
    
    # Bonus por contener la palabra completa más larga
    palabra_mas_larga = max(palabras_busqueda, key=len, default="")
    if palabra_mas_larga and palabra_mas_larga in producto_norm:
        puntuacion_base += 0.2
    
    # Limitar a 1.0 máximo
    return min(puntuacion_base, 1.0)

def buscar_producto(driver, nombre_producto):
    """
    Busca un producto en el sitio de Difarmer y navega a los detalles del producto.
    MEJORADO: Siempre toma el primer resultado y verifica similitud.
   
    Args:
        driver (webdriver.Chrome): Instancia del navegador con sesión iniciada
        nombre_producto (str): Nombre del producto a buscar
       
    Returns:
        bool: True si se encontró y accedió al detalle del producto, False en caso contrario
    """

    if not driver:
        logger.error("No se proporcionó un navegador válido")
        return False
   
    try:
        logger.info(f"🔍 Buscando producto: '{nombre_producto}'")
       
        # Buscar el campo de búsqueda
        search_field = None
        search_selectors = [
            "input[placeholder='¿Qué producto buscas?']",
            "input[type='search']",
            ".search-input",
            "input.form-control"
        ]
       
        for selector in search_selectors:
            fields = driver.find_elements(By.CSS_SELECTOR, selector)
            if fields and fields[0].is_displayed():
                search_field = fields[0]
                logger.info(f"✅ Campo de búsqueda encontrado con selector: {selector}")
                break
       
        if not search_field:
            logger.error("❌ No se pudo encontrar el campo de búsqueda")
            driver.save_screenshot("error_no_campo_busqueda.png")
            return False
       
        # Limpiar campo de búsqueda y escribir el nombre del producto
        search_field.clear()
        search_field.send_keys(nombre_producto)
      
        # Enviar la búsqueda presionando Enter
        search_field.send_keys(Keys.RETURN)
        logger.info(f"🚀 Búsqueda enviada para: '{nombre_producto}'")
       
        # Esperar a que carguen los resultados
        time.sleep(5)
      
        # Guardar captura de los resultados de búsqueda
        driver.save_screenshot("resultados_busqueda.png")
        
        # Guardar HTML para análisis
        with open("resultados_busqueda.html", "w", encoding="utf-8") as f:
            f.write(driver.page_source)
        logger.info("📄 HTML de resultados guardado para análisis")
       
        # ✅ NUEVA LÓGICA: Buscar CUALQUIER tarjeta de producto y tomar la primera
        logger.info("🎯 NUEVA ESTRATEGIA: Buscar y evaluar el primer producto disponible")
        
        # Buscar tarjetas de productos o elementos que contengan información de productos
        selectores_tarjetas = [
            # Basado en las imágenes, buscar divs que contengan productos
            "//div[contains(., 'Laboratorio:') and contains(., 'Mi precio:')]",
            "//div[contains(., 'Código Difarmer:')]",
            "//div[contains(@class, 'producto') or contains(@class, 'item') or contains(@class, 'card')]",
            "//div[.//img and contains(., '$')]",  # Divs con imagen y precio
            "//div[contains(., 'Existencia:')]",
            "//div[contains(., 'León:')]"  # León es donde está la existencia según las imágenes
        ]
        
        primera_tarjeta = None
        nombre_primer_producto = ""
        
        for selector in selectores_tarjetas:
            try:
                elementos = driver.find_elements(By.XPATH, selector)
                elementos_visibles = [elem for elem in elementos if elem.is_displayed()]
                
                if elementos_visibles:
                    logger.info(f"✅ Encontradas {len(elementos_visibles)} tarjetas con selector: {selector}")
                    primera_tarjeta = elementos_visibles[0]
                    
                    # Intentar extraer el nombre del producto de esta tarjeta
                    texto_tarjeta = primera_tarjeta.text
                    
                    # Buscar líneas que parezcan nombres de productos (con mayúsculas, MG, TABS, etc.)
                    lineas = texto_tarjeta.split('\n')
                    for linea in lineas:
                        if re.search(r'[A-Z]{3,}.*(?:MG|TABS|TAB|CAP|ML|G\b)', linea):
                            nombre_primer_producto = linea.strip()
                            logger.info(f"📝 Nombre extraído de tarjeta: '{nombre_primer_producto}'")
                            break
                    
                    # Si no encontramos con regex, usar la primera línea que tenga más de 10 caracteres
                    if not nombre_primer_producto:
                        for linea in lineas:
                            if len(linea.strip()) > 10 and not '$' in linea and not ':' in linea:
                                nombre_primer_producto = linea.strip()
                                logger.info(f"📝 Nombre extraído (línea larga): '{nombre_primer_producto}'")
                                break
                    
                    break
            except Exception as e:
                logger.warning(f"⚠️ Error con selector {selector}: {e}")
                continue
        
        # Si no encontramos tarjetas específicas, buscar cualquier texto que parezca nombre de producto
        if not primera_tarjeta:
            logger.info("🔍 No se encontraron tarjetas específicas, buscando nombres de productos en el texto general")
            
            # Buscar elementos que contengan nombres que parezcan medicamentos
            elementos_texto = driver.find_elements(By.XPATH, "//*[text()]")
            for elemento in elementos_texto:
                if elemento.is_displayed():
                    texto = elemento.text.strip()
                    # Buscar texto que parezca nombre de medicamento
                    if re.search(r'[A-Z]{3,}.*(?:MG|TABS|TAB|CAP|ML|G\b)', texto) and len(texto) > 5:
                        nombre_primer_producto = texto
                        primera_tarjeta = elemento
                        logger.info(f"📝 Nombre encontrado en texto general: '{nombre_primer_producto}'")
                        break
        
        # Verificar si tenemos un producto para evaluar
        if not nombre_primer_producto:
            logger.warning("❌ No se pudo extraer el nombre de ningún producto de los resultados")
            
            # Como último recurso, verificar si hay mensaje de "No se encontraron resultados"
            no_results_messages = driver.find_elements(By.XPATH, 
                "//*[contains(text(), 'No se encontraron resultados')]")
            
            for message in no_results_messages:
                if message.is_displayed():
                    logger.warning(f"❌ Mensaje de 'No resultados' confirmado para: '{nombre_producto}'")
                    driver.save_screenshot("no_resultados_confirmado.png")
                    return False
            
            # Si no hay mensaje explícito pero tampoco encontramos productos, asumir que no hay resultados
            logger.warning(f"❌ No se encontraron productos válidos para: '{nombre_producto}'")
            return False
        
        # ✅ CALCULAR SIMILITUD entre búsqueda y primer producto encontrado
        similitud = calcular_similitud_producto(nombre_producto, nombre_primer_producto)
        umbral_similitud = 0.4  # Umbral mínimo de similitud (40%)
        
        logger.info(f"🧮 EVALUACIÓN DE SIMILITUD:")
        logger.info(f"   Búsqueda: '{nombre_producto}'")
        logger.info(f"   Encontrado: '{nombre_primer_producto}'")
        logger.info(f"   Similitud: {similitud:.2f} (umbral: {umbral_similitud})")
        
        if similitud < umbral_similitud:
            logger.warning(f"❌ SIMILITUD INSUFICIENTE ({similitud:.2f} < {umbral_similitud})")
            logger.warning(f"   El producto encontrado '{nombre_primer_producto}' no es suficientemente similar a '{nombre_producto}'")
            driver.save_screenshot("similitud_insuficiente.png")
            return False
        
        logger.info(f"✅ SIMILITUD ACEPTABLE ({similitud:.2f} >= {umbral_similitud})")
        logger.info(f"   Procediendo a hacer clic en el producto: '{nombre_primer_producto}'")
        
        # ✅ HACER CLIC EN EL PRIMER PRODUCTO (que ya validamos que es similar)
        if primera_tarjeta:
            try:
                # Resaltar el elemento para depuración
                driver.execute_script("arguments[0].style.border='3px solid green'", primera_tarjeta)
                driver.save_screenshot("producto_seleccionado.png")
                
                # Intentar encontrar elementos clickeables dentro de la tarjeta
                elementos_clickeables = [
                    ".//a[contains(text(), 'Detalle de producto')]",
                    ".//img",
                    ".//a",
                    "."  # El elemento mismo como último recurso
                ]
                
                clic_exitoso = False
                for selector_click in elementos_clickeables:
                    try:
                        elemento_click = primera_tarjeta.find_element(By.XPATH, selector_click)
                        if elemento_click.is_displayed():
                            logger.info(f"🎯 Intentando hacer clic con selector: {selector_click}")
                            
                            # Scroll al elemento
                            driver.execute_script("arguments[0].scrollIntoView({block:'center'});", elemento_click)
                            time.sleep(1)
                            
                            # Intentar clic normal
                            try:
                                elemento_click.click()
                                clic_exitoso = True
                                logger.info(f"✅ Clic exitoso con selector: {selector_click}")
                                break
                            except:
                                # Intentar clic con JavaScript
                                driver.execute_script("arguments[0].click();", elemento_click)
                                clic_exitoso = True
                                logger.info(f"✅ Clic exitoso con JavaScript, selector: {selector_click}")
                                break
                    except Exception as e:
                        logger.warning(f"⚠️ Error con selector de clic {selector_click}: {e}")
                        continue
                
                if clic_exitoso:
                    # Esperar a que cargue la página de detalle
                    time.sleep(5)
                    driver.save_screenshot("despues_clic_exitoso.png")
                    
                    # Verificar que estamos en una página de detalle
                    url_actual = driver.current_url
                    texto_pagina = driver.page_source.lower()
                    
                    # Indicadores de que estamos en página de detalle
                    indicadores_detalle = [
                        'detalle' in url_actual.lower(),
                        'producto' in url_actual.lower(),
                        'mi precio:' in texto_pagina,
                        'código difarmer:' in texto_pagina,
                        'laboratorio:' in texto_pagina
                    ]
                    
                    if any(indicadores_detalle):
                        logger.info(f"✅ ¡ÉXITO! Navegación exitosa a página de detalle")
                        logger.info(f"   URL: {url_actual}")
                        return True
                    else:
                        logger.warning(f"⚠️ Clic realizado pero no parece ser página de detalle")
                        logger.warning(f"   URL: {url_actual}")
                        # Aún así, intentemos extraer información
                        return True
                else:
                    logger.error(f"❌ No se pudo hacer clic en ningún elemento de la tarjeta")
                    return False
                    
            except Exception as e:
                logger.error(f"❌ Error durante el clic en el producto: {e}")
                driver.save_screenshot("error_clic_producto.png")
                return False
        else:
            logger.error(f"❌ No hay tarjeta de producto para hacer clic")
            return False
       
    except Exception as e:
        logger.error(f"❌ Error durante la búsqueda del producto: {e}")
        driver.save_screenshot("error_busqueda_general.png")
        return False
