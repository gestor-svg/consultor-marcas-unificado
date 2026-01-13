"""
IMPI Buscador Por Denominación - Búsqueda Simple
==================================================

Búsqueda en el IMPI usando el formulario de búsqueda por denominación.
Este es el método SIMPLE usado en el funnel público para análisis rápido.

URL: https://acervomarcas.impi.gob.mx:8181/marcanet/vistas/common/home.pgi
Formulario: frmBsqDen (Búsqueda por Denominación)

Autor: Gestor SVG / MarcaSegura
Fecha: Enero 2026
"""

import requests
from bs4 import BeautifulSoup
import re
import logging

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def normalizar_marca(marca: str) -> str:
    """Normaliza el nombre de la marca para búsqueda"""
    marca = marca.strip()
    marca = re.sub(r'\s+', ' ', marca)
    return marca


def buscar_impi_denominacion(marca: str) -> str:
    """
    Búsqueda simple en IMPI usando JSF/PrimeFaces AJAX
    
    Args:
        marca: Nombre de la marca a buscar
        
    Returns:
        str: Uno de los siguientes valores:
            - "POSIBLEMENTE_DISPONIBLE": No se encontraron resultados
            - "REQUIERE_ANALISIS": Se encontraron marcas similares/iguales
            - "ERROR_CONEXION": Hubo un problema con la conexión
    """
    session_req = requests.Session()
    session_req.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'Accept-Language': 'es-MX,es;q=0.9,en;q=0.8',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
    })
    
    marca_buscar = normalizar_marca(marca)
    
    logger.info(f"\n{'='*60}")
    logger.info(f"[IMPI DENOMINACIÓN] Buscando marca: '{marca_buscar}'")
    logger.info(f"{'='*60}")
    
    try:
        # PASO 1: Obtener ViewState
        url_base = "https://acervomarcas.impi.gob.mx:8181/marcanet/"
        response_inicial = session_req.get(url_base, timeout=30, verify=True)
        
        if response_inicial.status_code != 200:
            logger.error(f"[IMPI] Error de conexión: {response_inicial.status_code}")
            return "ERROR_CONEXION"
        
        soup_inicial = BeautifulSoup(response_inicial.text, 'html.parser')
        viewstate_input = soup_inicial.find('input', {'name': 'javax.faces.ViewState'})
        
        if not viewstate_input:
            logger.error("[IMPI] No se encontró ViewState")
            return "ERROR_CONEXION"
        
        viewstate = viewstate_input.get('value', '')
        
        # PASO 2: Búsqueda AJAX por denominación
        url_busqueda = "https://acervomarcas.impi.gob.mx:8181/marcanet/vistas/common/home.pgi"
        
        data_busqueda = {
            'javax.faces.partial.ajax': 'true',
            'javax.faces.source': 'frmBsqDen:busquedaIdButton',
            'javax.faces.partial.execute': 'frmBsqDen:busquedaIdButton frmBsqDen:denominacionId frmBsqDen:swtExacto',
            'javax.faces.partial.render': 'frmBsqDen',
            'frmBsqDen:busquedaIdButton': 'frmBsqDen:busquedaIdButton',
            'frmBsqDen': 'frmBsqDen',
            'frmBsqDen:denominacionId': marca_buscar,
            'javax.faces.ViewState': viewstate,
        }
        
        headers_ajax = {
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
            'Faces-Request': 'partial/ajax',
            'X-Requested-With': 'XMLHttpRequest',
            'Origin': 'https://acervomarcas.impi.gob.mx:8181',
            'Referer': url_base,
        }
        
        response_busqueda = session_req.post(
            url_busqueda, 
            data=data_busqueda, 
            headers=headers_ajax, 
            timeout=30
        )
        
        if response_busqueda.status_code != 200:
            logger.error(f"[IMPI] Error en búsqueda: {response_busqueda.status_code}")
            return "ERROR_CONEXION"
        
        # PASO 3: Analizar respuesta
        respuesta_texto = response_busqueda.text
        texto_lower = respuesta_texto.lower()
        
        # Detectar resultados por "Total de registros"
        match_total = re.search(r'total de registros\s*=\s*(\d+)', texto_lower)
        if match_total and int(match_total.group(1)) > 0:
            total_registros = int(match_total.group(1))
            logger.info(f"[IMPI] ✗ MARCA ENCONTRADA - {total_registros} registros")
            return "REQUIERE_ANALISIS"
        
        # Detectar resultados por filas en la tabla
        if 'frmBsqDen:resultadoExpediente_data' in respuesta_texto:
            filas = re.findall(r'ui-datatable-(even|odd)', respuesta_texto)
            if filas:
                logger.info(f"[IMPI] ✗ MARCA ENCONTRADA - {len(filas)} filas en tabla")
                return "REQUIERE_ANALISIS"
        
        # Detectar por palabras clave de marca registrada
        indicadores = ['registro de marca', 'nominativa', 'mixta']
        if sum(1 for i in indicadores if i in texto_lower) >= 2:
            if marca_buscar.lower() in texto_lower:
                logger.info(f"[IMPI] ✗ MARCA ENCONTRADA - Indicadores detectados")
                return "REQUIERE_ANALISIS"
        
        # Detectar mensaje de "sin resultados"
        if 'ui-datatable-empty-message' in respuesta_texto:
            logger.info(f"[IMPI] ✓ MARCA POSIBLEMENTE DISPONIBLE")
            return "POSIBLEMENTE_DISPONIBLE"
        
        # Si la respuesta es muy grande, probablemente hay resultados
        if len(respuesta_texto) > 5000:
            logger.warning(f"[IMPI] Respuesta grande ({len(respuesta_texto)} bytes) - Asumiendo resultados")
            return "REQUIERE_ANALISIS"
        
        # Por defecto, requiere análisis
        logger.warning(f"[IMPI] Estado indeterminado - Requiere análisis por seguridad")
        return "REQUIERE_ANALISIS"
        
    except requests.Timeout:
        logger.error(f"[IMPI] Timeout en la búsqueda")
        return "ERROR_CONEXION"
    except requests.ConnectionError as e:
        logger.error(f"[IMPI] Error de conexión: {e}")
        return "ERROR_CONEXION"
    except Exception as e:
        logger.error(f"[IMPI] Error inesperado: {e}")
        return "ERROR_CONEXION"


if __name__ == "__main__":
    # Prueba del módulo
    test_marca = "CAFE LUNA"
    print(f"\n🧪 Probando búsqueda por denominación: {test_marca}")
    resultado = buscar_impi_denominacion(test_marca)
    print(f"Resultado: {resultado}\n")
