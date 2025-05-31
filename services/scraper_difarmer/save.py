#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import time
import re
import json

from .settings import logger

def guardar_resultados(info_producto, nombre_archivo=None):
    """
    Guarda la información del producto en un archivo JSON.
   
    Args:
        info_producto (dict): Información del producto
        nombre_archivo (str, optional): Nombre del archivo de salida
    """
    if not info_producto:
        logger.warning("No hay información para guardar")
        return
   
    # Verificar que info_producto sea un diccionario
    if not isinstance(info_producto, dict):
        logger.error(f"Error: info_producto no es un diccionario, es {type(info_producto)}")
        return
   
    if not nombre_archivo:
        # Generar nombre de archivo basado en el nombre del producto
        nombre_base = info_producto.get('nombre', 'producto')
        # Verificar que nombre_base sea un string
        if not isinstance(nombre_base, str):
            nombre_base = 'producto'
        nombre_base = re.sub(r'[\\/*?:"<>|]', '', nombre_base)  # Eliminar caracteres inválidos para nombres de archivo
        nombre_archivo = f"{nombre_base}_{int(time.time())}.json"
   
    try:
        with open(nombre_archivo, 'w', encoding='utf-8') as f:
            json.dump(info_producto, f, ensure_ascii=False, indent=4)
        logger.info(f"Información guardada en: {nombre_archivo}")
        
        # Imprimir información en consola
        print("\n=== INFORMACIÓN DEL MEDICAMENTO ===")
        
        # Mostrar información de forma ordenada
        campos_orden = [
            'nombre', 'laboratorio', 'principio_activo', 'registro_sanitario',
            'codigo_barras', 'codigo_sat', 'codigo_difarmer', 
            'precio_publico', 'mi_precio', 'existencia'  # Campos actualizados
        ]
        
        for campo in campos_orden:
            if campo in info_producto and info_producto[campo]:
                print(f"{campo.replace('_', ' ').title()}: {info_producto[campo]}")
        
        # Mostrar URL e imagen al final
        if 'url' in info_producto and info_producto['url']:
            print(f"URL: {info_producto['url']}")
        
        if 'imagen' in info_producto and info_producto['imagen']:
            print(f"Imagen: {info_producto['imagen']}")
            
    except Exception as e:
        logger.error(f"Error al guardar la información: {e}")
