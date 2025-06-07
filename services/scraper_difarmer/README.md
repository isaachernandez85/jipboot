# Scraper Difarmer

Este paquete proporciona funcionalidades para extraer información de productos farmacéuticos desde el sitio web de Difarmer.

## Instalación

```bash
# Clona el repositorio
git clone https://github.com/tu-usuario/scraper_difarmer.git
cd scraper_difarmer

# Instala las dependencias
pip install -r requirements.txt
```

## Uso

### Como script independiente

```bash
# Ejecutar el script directamente (modo interactivo)
python main.py

# O proporcionar el nombre del medicamento como argumento
python main.py "DUALGOS TABS"
```

### Como módulo importado

```python
from scraper_difarmer import buscar_info_medicamento, guardar_resultados

# Buscar información de un medicamento (por defecto en modo headless)
info = buscar_info_medicamento("DUALGOS TABS")

# Para desarrollo local sin headless
# info = buscar_info_medicamento("DUALGOS TABS", headless=False)

# Si se encontró información, guardarla
if info:
    guardar_resultados(info, "resultado_dualgos.json")
```

## Ejecución en entorno de servidor

Este paquete está optimizado para funcionar en entornos sin interfaz gráfica como servidores o contenedores. Para asegurar el correcto funcionamiento:

1. Instalar Chrome/Chromium en el servidor/contenedor:
   ```bash
   # Para sistemas basados en Debian/Ubuntu
   apt-get update && apt-get install -y chromium-browser
   
   # Para sistemas basados en Alpine
   apk add --no-cache chromium
   ```

2. Definir una variable de entorno `CHROME_BINARY_LOCATION` si es necesario apuntar a una ubicación específica del ejecutable de Chrome.

## Estructura del proyecto

- `__init__.py`: Define el paquete y expone las funciones principales
- `settings.py`: Configuración global (credenciales, etc.)
- `login.py`: Maneja el inicio de sesión en el sitio
- `search.py`: Implementa la búsqueda de productos
- `extract.py`: Extrae información detallada del producto
- `save.py`: Guarda los resultados en formato JSON
- `main.py`: Punto de entrada principal

## Notas de uso

- Para entornos de producción, el modo headless está activado por defecto.
- Para desarrollo, puedes definir la variable de entorno `ENVIRONMENT=development` para desactivar el modo headless.
