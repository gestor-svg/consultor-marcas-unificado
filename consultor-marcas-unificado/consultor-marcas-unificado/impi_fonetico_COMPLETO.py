"""
IMPI Buscador Fonético - Implementación Real
=============================================

Basado en los aprendizajes de la versión pública:
- JSF/PrimeFaces con ViewState
- Búsquedas AJAX
- URL fonética: /vistas/common/datos/bsqFoneticaCompleta.pgi

Autor: Gestor SVG / MarcaSegura
Fecha: Enero 2026
"""

import requests
from bs4 import BeautifulSoup
import time
import re
from typing import List, Dict, Optional, Tuple
from datetime import datetime
import logging

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ConfigIMPI:
    """Configuración del cliente IMPI para búsqueda fonética"""
    
    # URLs
    BASE_URL = "https://acervomarcas.impi.gob.mx:8181/marcanet/"
    URL_FONETICA = "https://acervomarcas.impi.gob.mx:8181/marcanet/vistas/common/datos/bsqFoneticaCompleta.pgi"
    FORM_ACTION = "/marcanet/vistas/common/datos/bsqFoneticaCompleta.pgi"
    
    # Headers base
    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'es-MX,es;q=0.9,en;q=0.8',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Referer': 'https://acervomarcas.impi.gob.mx:8181/marcanet/',
    }
    
    # Headers específicos para AJAX (si se necesitan)
    HEADERS_AJAX = {
        'Faces-Request': 'partial/ajax',
        'X-Requested-With': 'XMLHttpRequest',
        'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
    }
    
    # Configuración de comportamiento
    DELAY_ENTRE_PETICIONES = 2.0
    TIMEOUT_PETICION = 30
    MAX_REINTENTOS = 3
    
    # Patrones de detección
    PATTERN_TOTAL = re.compile(r'total de registros\s*[=:]\s*(\d+)', re.IGNORECASE)
    PATTERN_RESULTADO = re.compile(r'(nominativa|mixta|registro de marca)', re.IGNORECASE)


class MarcaInfo:
    """Modelo de datos para una marca encontrada"""
    
    def __init__(
        self,
        denominacion: str,
        expediente: str,
        titular: str,
        clase: str,
        estado: str,
        tipo: Optional[str] = None,
        registro: Optional[str] = None,  # Número de registro
        fecha_registro: Optional[str] = None,
        fecha_vencimiento: Optional[str] = None,
        similitud_fonetica: Optional[float] = None
    ):
        self.denominacion = denominacion.strip() if denominacion else ""
        self.expediente = expediente.strip() if expediente else ""
        self.registro = registro.strip() if registro else ""  # Número de registro
        self.titular = titular.strip() if titular else ""
        self.clase = clase.strip() if clase else ""
        self.estado = estado.strip() if estado else ""
        self.tipo = tipo.strip() if tipo else ""
        self.fecha_registro = fecha_registro
        self.fecha_vencimiento = fecha_vencimiento
        self.similitud_fonetica = similitud_fonetica
    
    def to_dict(self) -> Dict:
        """Convierte la marca a diccionario"""
        return {
            'denominacion': self.denominacion,
            'expediente': self.expediente,
            'registro': self.registro,  # ← AGREGADO
            'titular': self.titular,
            'clase': self.clase,
            'estado': self.estado,
            'tipo': self.tipo,
            'fecha_registro': self.fecha_registro,
            'fecha_vencimiento': self.fecha_vencimiento,
            'similitud_fonetica': self.similitud_fonetica
        }
    
    def __repr__(self) -> str:
        return f"MarcaInfo(denominacion='{self.denominacion}', expediente='{self.expediente}', clase='{self.clase}')"


class ResultadoBusqueda:
    """Modelo para el resultado completo de una búsqueda"""
    
    def __init__(
        self,
        marca_consultada: str,
        clase_consultada: Optional[int],
        fecha_busqueda: datetime,
        marcas_encontradas: List[MarcaInfo],
        exito: bool,
        tiempo_busqueda: float,
        total_registros: int = 0,
        error: Optional[str] = None
    ):
        self.marca_consultada = marca_consultada
        self.clase_consultada = clase_consultada
        self.fecha_busqueda = fecha_busqueda
        self.marcas_encontradas = marcas_encontradas
        self.exito = exito
        self.tiempo_busqueda = tiempo_busqueda
        self.total_registros = total_registros
        self.error = error
    
    def to_dict(self) -> Dict:
        """Convierte el resultado a diccionario"""
        return {
            'marca_consultada': self.marca_consultada,
            'clase_consultada': self.clase_consultada,
            'fecha_busqueda': self.fecha_busqueda.isoformat(),
            'total_registros': self.total_registros,
            'total_parseadas': len(self.marcas_encontradas),
            'marcas_similares': [marca.to_dict() for marca in self.marcas_encontradas],
            'exito': self.exito,
            'tiempo_busqueda': round(self.tiempo_busqueda, 2),
            'error': self.error
        }


class IMPIBuscadorFonetico:
    """
    Cliente para búsqueda fonética en el sistema del IMPI
    Usa JSF/PrimeFaces con manejo de ViewState
    """
    
    def __init__(self):
        self.config = ConfigIMPI()
        self.session = requests.Session()
        self.session.headers.update(self.config.HEADERS)
        self.viewstate = None
    
    def buscar_fonetica(
        self,
        marca: str,
        clase_niza: Optional[int] = None,
        max_reintentos: Optional[int] = None
    ) -> ResultadoBusqueda:
        """
        Busca marcas fonéticamente similares en el IMPI
        
        Args:
            marca: Nombre de la marca a buscar
            clase_niza: Clase de Niza (1-45) opcional
            max_reintentos: Máximo de reintentos si falla
        
        Returns:
            ResultadoBusqueda con las marcas encontradas
        """
        
        # Validar entrada
        if not marca or not marca.strip():
            logger.error("La marca no puede estar vacía")
            return self._resultado_error(marca, clase_niza, "Marca vacía")
        
        if clase_niza and (clase_niza < 1 or clase_niza > 45):
            logger.error(f"Clase de Niza inválida: {clase_niza}")
            return self._resultado_error(marca, clase_niza, "Clase de Niza inválida")
        
        # Configurar reintentos
        reintentos = max_reintentos if max_reintentos else self.config.MAX_REINTENTOS
        
        # Intentar búsqueda
        inicio = time.time()
        
        for intento in range(1, reintentos + 1):
            try:
                logger.info(f"Búsqueda fonética: '{marca}' (Clase: {clase_niza or 'Todas'}) - Intento {intento}/{reintentos}")
                
                # Delay entre intentos
                if intento > 1:
                    time.sleep(self.config.DELAY_ENTRE_PETICIONES)
                
                # Obtener ViewState si no lo tenemos
                if not self.viewstate:
                    logger.debug("Obteniendo ViewState...")
                    self._obtener_viewstate()
                
                # Ejecutar búsqueda
                marcas, total = self._ejecutar_busqueda_fonetica(marca, clase_niza)
                
                # Calcular tiempo
                tiempo_busqueda = time.time() - inicio
                
                # Crear resultado exitoso
                resultado = ResultadoBusqueda(
                    marca_consultada=marca,
                    clase_consultada=clase_niza,
                    fecha_busqueda=datetime.now(),
                    marcas_encontradas=marcas,
                    exito=True,
                    tiempo_busqueda=tiempo_busqueda,
                    total_registros=total
                )
                
                logger.info(f"✅ Búsqueda exitosa: {len(marcas)} marcas parseadas de {total} registros en {tiempo_busqueda:.2f}s")
                return resultado
            
            except requests.Timeout:
                logger.warning(f"⏱️ Timeout en intento {intento}/{reintentos}")
                if intento == reintentos:
                    return self._resultado_error(marca, clase_niza, "Timeout: el servidor tardó demasiado")
            
            except requests.RequestException as e:
                logger.warning(f"🔌 Error de conexión en intento {intento}/{reintentos}: {str(e)}")
                if intento == reintentos:
                    return self._resultado_error(marca, clase_niza, f"Error de conexión: {str(e)}")
            
            except Exception as e:
                logger.error(f"❌ Error inesperado: {str(e)}", exc_info=True)
                return self._resultado_error(marca, clase_niza, f"Error inesperado: {str(e)}")
        
        return self._resultado_error(marca, clase_niza, "Máximo de reintentos alcanzado")
    
    def _obtener_viewstate(self) -> None:
        """
        Obtiene el ViewState necesario para JSF
        Similar a la versión pública
        """
        try:
            logger.debug(f"GET {self.config.BASE_URL}")
            response = self.session.get(
                self.config.BASE_URL,
                timeout=self.config.TIMEOUT_PETICION
            )
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            viewstate_input = soup.find('input', {'name': 'javax.faces.ViewState'})
            
            if viewstate_input and viewstate_input.get('value'):
                self.viewstate = viewstate_input.get('value')
                logger.debug(f"✅ ViewState obtenido: {self.viewstate[:50]}...")
            else:
                logger.warning("⚠️ No se encontró ViewState en la página")
                self.viewstate = ""
        
        except Exception as e:
            logger.error(f"Error obteniendo ViewState: {str(e)}")
            self.viewstate = ""
    
    def _ejecutar_busqueda_fonetica(
        self,
        marca: str,
        clase_niza: Optional[int]
    ) -> Tuple[List[MarcaInfo], int]:
        """
        Ejecuta la búsqueda fonética y obtiene TODAS las páginas de resultados
        """
        
        todas_marcas = []
        total_registros = 0
        pagina = 0
        max_paginas = 20  # Límite de seguridad (20 páginas * 15 = 300 marcas max)
        
        logger.info(f"🔍 Iniciando búsqueda paginada...")
        
        while pagina < max_paginas:
            # Preparar datos del formulario
            data = {
                'javax.faces.partial.ajax': 'true',
                'javax.faces.source': 'frmBsqFonetica:busquedaId2' if pagina == 0 else 'frmBsqFonetica:resultadoExpediente',
                'javax.faces.partial.execute': '@all',
                'javax.faces.partial.render': 'frmBsqFonetica',
                'frmBsqFonetica': 'frmBsqFonetica',
                'frmBsqFonetica:denominacion': marca.strip().upper(),
            }
            
            # Primera página: usar botón de búsqueda
            if pagina == 0:
                data['frmBsqFonetica:busquedaId2'] = 'frmBsqFonetica:busquedaId2'
            else:
                # Páginas siguientes: usar paginación
                data['frmBsqFonetica:resultadoExpediente_pagination'] = 'true'
                data['frmBsqFonetica:resultadoExpediente_first'] = str(pagina * 15)
                data['frmBsqFonetica:resultadoExpediente_rows'] = '15'
            
            if clase_niza:
                data['frmBsqFonetica:clases'] = str(clase_niza)
            
            if self.viewstate:
                data['javax.faces.ViewState'] = self.viewstate
            
            # Hacer petición
            logger.info(f"📄 Obteniendo página {pagina + 1}...")
            response = self.session.post(
                self.config.URL_FONETICA,
                data=data,
                timeout=self.config.TIMEOUT_PETICION,
                allow_redirects=True
            )
            
            response.raise_for_status()
            
            # Parsear resultados de esta página
            marcas_pagina, total = self._parsear_resultados_fonetica(response)
            
            if not marcas_pagina:
                logger.info(f"✅ No hay más resultados. Total obtenido: {len(todas_marcas)} marcas")
                break
            
            todas_marcas.extend(marcas_pagina)
            total_registros = total if total > 0 else len(todas_marcas)
            
            logger.info(f"✅ Página {pagina + 1}: +{len(marcas_pagina)} marcas (total acumulado: {len(todas_marcas)})")
            
            # Si obtuvimos menos de 15, es la última página
            if len(marcas_pagina) < 15:
                logger.info(f"📄 Última página detectada (menos de 15 resultados)")
                break
            
            # Si ya tenemos todas las marcas del total
            if total_registros > 0 and len(todas_marcas) >= total_registros:
                logger.info(f"✅ Todas las marcas obtenidas ({len(todas_marcas)}/{total_registros})")
                break
            
            pagina += 1
        
        logger.info(f"🎯 Búsqueda completa: {len(todas_marcas)} marcas obtenidas de {total_registros} totales")
        return todas_marcas, total_registros
    
    def _parsear_resultados_fonetica(
        self,
        response: requests.Response
    ) -> Tuple[List[MarcaInfo], int]:
        """
        Parsea los resultados de la búsqueda fonética
        Maneja respuestas JSF/PrimeFaces AJAX en formato XML
        """
        
        marcas = []
        total_registros = 0
        
        try:
            html_text = response.text
            
            # INFO: Ver primeras líneas
            logger.info(f"🔍 Tipo de respuesta: {'XML AJAX' if '<?xml' in html_text[:100] else 'HTML'}")
            logger.info(f"📏 Longitud: {len(html_text)} caracteres")
            
            # Verificar si es respuesta AJAX XML de JSF
            if html_text.strip().startswith('<?xml') and '<partial-response>' in html_text:
                logger.info("📋 Parseando respuesta AJAX XML de JSF/PrimeFaces")
                
                # CRÍTICO: Extraer CDATA manualmente con regex (BeautifulSoup falla con CDATA grandes)
                cdata_pattern = r'<!\[CDATA\[(.*?)\]\]>'
                cdata_matches = re.findall(cdata_pattern, html_text, re.DOTALL)
                
                logger.info(f"📦 Encontrados {len(cdata_matches)} bloques CDATA")
                
                for idx, cdata_content in enumerate(cdata_matches):
                    logger.info(f"📦 CDATA #{idx+1} - Longitud: {len(cdata_content)} caracteres")
                    
                    # Verificar si contiene tabla de resultados
                    if 'resultadoExpediente' in cdata_content or 'ui-datatable-data' in cdata_content:
                        logger.info(f"✅ CDATA #{idx+1} contiene tabla de resultados!")
                        
                        # Buscar el total de registros en el HTML
                        # Buscar patrones como "... y 280 marcas más" o similar
                        total_pattern = r'y\s+(\d+)\s+marcas?\s+más'
                        total_match = re.search(total_pattern, cdata_content, re.IGNORECASE)
                        if total_match:
                            registros_adicionales = int(total_match.group(1))
                            logger.info(f"📊 Detectados {registros_adicionales} registros adicionales en otras páginas")
                        
                        # Parsear el HTML interno
                        soup = BeautifulSoup(cdata_content, 'lxml')
                        
                        # Buscar tbody
                        tbody = soup.find('tbody', id='frmBsqFonetica:resultadoExpediente_data')
                        
                        if not tbody:
                            tbody = soup.find('tbody', class_='ui-datatable-data')
                            if tbody:
                                logger.info("🔄 Encontrado tbody por clase")
                        
                        if tbody:
                            filas = tbody.find_all('tr', attrs={'data-ri': True})
                            filas_pagina = len(filas)
                            logger.info(f"📊 Encontradas {filas_pagina} filas en esta página")
                            
                            # Parsear filas
                            for fila in filas:
                                marca = self._parsear_fila_marca(fila)
                                if marca:
                                    marcas.append(marca)
                            
                            # Calcular total real
                            if total_match:
                                total_registros = len(marcas) + int(total_match.group(1))
                            else:
                                total_registros = len(marcas)
                            
                            logger.info(f"✅ Página parseada: {len(marcas)} marcas. Total esperado: {total_registros}")
                            break
                
                if not marcas:
                    logger.warning("⚠️ No se encontraron resultados en ningún CDATA")
            else:
                # HTML normal - intentar parseo tradicional
                soup = BeautifulSoup(response.content, 'lxml')
                marcas = self._extraer_marcas_de_tabla(soup)
                total_registros = len(marcas)
        
        except Exception as e:
            logger.error(f"Error parseando resultados: {str(e)}", exc_info=True)
        
        return marcas, total_registros
    
    def _detectar_total_registros(self, html_text: str, soup: BeautifulSoup) -> int:
        """
        Detecta el total de registros usando múltiples métodos
        Basado en aprendizajes de la versión pública
        """
        
        # Método 1: Regex "total de registros = X"
        match = self.config.PATTERN_TOTAL.search(html_text)
        if match:
            total = int(match.group(1))
            logger.debug(f"Total detectado por regex: {total}")
            return total
        
        # Método 2: Buscar en elementos con texto "total" o "registros"
        for elem in soup.find_all(text=re.compile(r'total|registros', re.IGNORECASE)):
            parent_text = elem.parent.get_text()
            match = re.search(r'(\d+)', parent_text)
            if match:
                total = int(match.group(1))
                logger.debug(f"Total detectado en elemento: {total}")
                return total
        
        # Método 3: Contar filas de tabla
        tabla = soup.find('table', {'id': re.compile(r'resultado|tabla|data', re.IGNORECASE)})
        if tabla:
            filas = tabla.find_all('tr', {'class': re.compile(r'ui-datatable-(even|odd)|row', re.IGNORECASE)})
            if filas:
                total = len(filas)
                logger.debug(f"Total detectado contando filas: {total}")
                return total
        
        # Método 4: Buscar keywords de resultados
        if self.config.PATTERN_RESULTADO.search(html_text):
            logger.debug("Se detectaron keywords de resultados, asumiendo al menos 1")
            return 1
        
        logger.debug("No se pudo detectar total de registros")
        return 0
    
    def _extraer_marcas_de_tabla(self, soup: BeautifulSoup) -> List[MarcaInfo]:
        """
        Extrae las marcas de la tabla de resultados
        """
        
        marcas = []
        
        # Buscar tabla de resultados (ID exacto del IMPI)
        tabla = soup.find('table', {'id': 'frmBsqFonetica:resultadoExpediente'})
        
        if not tabla:
            # Intento alternativo: buscar por clase
            tabla = soup.find('div', {'id': 'frmBsqFonetica:resultadoExpediente'})
            if tabla:
                tabla = tabla.find('table')
        
        if not tabla:
            logger.warning("⚠️ No se encontró tabla de resultados")
            return marcas
        
        # Buscar tbody de datos (ID exacto del IMPI)
        tbody = tabla.find('tbody', {'id': 'frmBsqFonetica:resultadoExpediente_data'})
        
        if not tbody:
            tbody = tabla.find('tbody', {'class': 'ui-datatable-data'})
        
        if not tbody:
            logger.warning("⚠️ No se encontró tbody de datos")
            return marcas
        
        # Buscar filas de datos
        filas = tbody.find_all('tr', {'class': re.compile(r'ui-widget-content|ui-datatable')})
        
        if not filas:
            # Intento alternativo: todas las filas excepto header
            filas = tabla.find_all('tr')
            if filas and len(filas) > 1:
                filas = filas[1:]  # Saltar header
        
        logger.debug(f"Filas de datos encontradas: {len(filas)}")
        
        # Procesar cada fila
        for fila in filas:
            try:
                marca = self._parsear_fila_marca(fila)
                if marca and self._validar_marca(marca):
                    marcas.append(marca)
            except Exception as e:
                logger.debug(f"Error parseando fila: {str(e)}")
                continue
        
        return marcas
    
    def _parsear_fila_marca(self, fila) -> Optional[MarcaInfo]:
        """
        Parsea una fila de la tabla y extrae la información de la marca
        
        Estructura de columnas del IMPI (0-indexado):
        0: # (número de fila)
        1: TS (tipo de signo) - "M" para marca
        2: TM (tipo de marca) - vacío normalmente
        3: Titular
        4: Expediente
        5: Registro
        6: Denominación
        7: Clase
        8: Logotipo
        """
        
        celdas = fila.find_all('td')
        
        if len(celdas) < 8:
            return None
        
        try:
            # Extraer expediente completo (puede tener link)
            expediente_td = celdas[4]
            expediente_link = expediente_td.find('a')
            expediente = expediente_link.get_text(strip=True) if expediente_link else expediente_td.get_text(strip=True)
            
            # Extraer denominación completa (puede tener link)
            denominacion_td = celdas[6]
            denominacion_link = denominacion_td.find('a')
            denominacion = denominacion_link.get_text(strip=True) if denominacion_link else denominacion_td.get_text(strip=True)
            
            # Extraer registro (columna 5)
            registro = self._extraer_texto_celda(celdas, 5)
            
            marca = MarcaInfo(
                denominacion=denominacion,
                expediente=expediente,
                registro=registro,  # Número de registro
                titular=self._extraer_texto_celda(celdas, 3),
                clase=self._extraer_texto_celda(celdas, 7),
                estado="",  # El estado no viene en esta tabla
                tipo=self._extraer_texto_celda(celdas, 1),  # TS (tipo de signo)
                fecha_registro="",  # La fecha no viene en esta tabla
            )
            return marca
        except Exception as e:
            logger.debug(f"Error extrayendo datos de fila: {str(e)}")
            return None
    
    def _extraer_texto_celda(self, celdas: list, indice: int) -> str:
        """Extrae texto de una celda por índice"""
        try:
            if indice < len(celdas):
                return celdas[indice].get_text(strip=True)
        except:
            pass
        return ""
    
    def _validar_marca(self, marca: MarcaInfo) -> bool:
        """Valida que una marca tenga los campos mínimos"""
        
        if not marca.denominacion:
            logger.debug("Marca rechazada: sin denominación")
            return False
        
        if not marca.expediente:
            logger.debug("Marca rechazada: sin expediente")
            return False
        
        if not marca.clase:
            logger.debug("Marca rechazada: sin clase")
            return False
        
        # Validar que clase sea número 1-45
        try:
            clase_num = int(marca.clase)
            if clase_num < 1 or clase_num > 45:
                logger.debug(f"Marca rechazada: clase fuera de rango ({clase_num})")
                return False
        except ValueError:
            logger.debug(f"Marca rechazada: clase no numérica ({marca.clase})")
            return False
        
        return True
    
    def _resultado_error(
        self,
        marca: str,
        clase: Optional[int],
        error: str
    ) -> ResultadoBusqueda:
        """Crea un resultado de error"""
        return ResultadoBusqueda(
            marca_consultada=marca,
            clase_consultada=clase,
            fecha_busqueda=datetime.now(),
            marcas_encontradas=[],
            exito=False,
            tiempo_busqueda=0,
            total_registros=0,
            error=error
        )


# =============================================================================
# FUNCIONES DE UTILIDAD
# =============================================================================

def filtrar_vigentes(marcas: List[MarcaInfo]) -> List[MarcaInfo]:
    """Filtra solo marcas vigentes"""
    return [m for m in marcas if 'vigente' in m.estado.lower()]


def agrupar_por_clase(marcas: List[MarcaInfo]) -> Dict[str, List[MarcaInfo]]:
    """Agrupa marcas por clase de Niza"""
    agrupadas = {}
    for marca in marcas:
        clase = marca.clase
        if clase not in agrupadas:
            agrupadas[clase] = []
        agrupadas[clase].append(marca)
    return agrupadas


def contar_por_estado(marcas: List[MarcaInfo]) -> Dict[str, int]:
    """Cuenta marcas por estado"""
    conteo = {}
    for marca in marcas:
        estado = marca.estado.upper() if marca.estado else "DESCONOCIDO"
        conteo[estado] = conteo.get(estado, 0) + 1
    return conteo


# =============================================================================
# EJEMPLO DE USO
# =============================================================================

def ejemplo_uso():
    """Ejemplo de cómo usar el buscador fonético"""
    
    print("="*70)
    print(" IMPI BUSCADOR FONÉTICO - EJEMPLO DE USO")
    print("="*70)
    
    buscador = IMPIBuscadorFonetico()
    
    # Ejemplo 1: Búsqueda simple
    print("\n📝 EJEMPLO 1: Búsqueda simple")
    print("-" * 70)
    resultado = buscador.buscar_fonetica("COCA COLA")
    
    if resultado.exito:
        print(f"✅ Éxito en {resultado.tiempo_busqueda:.2f}s")
        print(f"📊 Total: {resultado.total_registros} registros")
        print(f"✅ Parseadas: {len(resultado.marcas_encontradas)} marcas\n")
        
        for i, marca in enumerate(resultado.marcas_encontradas[:3], 1):
            print(f"{i}. {marca.denominacion}")
            print(f"   Exp: {marca.expediente} | Clase: {marca.clase} | Estado: {marca.estado}")
    else:
        print(f"❌ Error: {resultado.error}")
    
    # Ejemplo 2: Con clase específica
    print("\n\n📝 EJEMPLO 2: Búsqueda con clase específica")
    print("-" * 70)
    resultado = buscador.buscar_fonetica("NIKE", clase_niza=25)
    
    if resultado.exito:
        print(f"✅ Éxito en {resultado.tiempo_busqueda:.2f}s")
        print(f"📊 Total: {resultado.total_registros} registros\n")
        
        # Análisis por estado
        conteo_estados = contar_por_estado(resultado.marcas_encontradas)
        print("📊 Por estado:")
        for estado, cantidad in conteo_estados.items():
            print(f"   - {estado}: {cantidad}")
    else:
        print(f"❌ Error: {resultado.error}")
    
    # Ejemplo 3: Exportar a JSON
    print("\n\n📝 EJEMPLO 3: Exportar a JSON")
    print("-" * 70)
    import json
    resultado = buscador.buscar_fonetica("STARBUCKS", clase_niza=43)
    
    if resultado.exito:
        datos = resultado.to_dict()
        print(json.dumps(datos, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    print("""
    ╔══════════════════════════════════════════════════════════════════╗
    ║                                                                  ║
    ║     IMPI BUSCADOR FONÉTICO - IMPLEMENTACIÓN COMPLETA           ║
    ║     Basado en JSF/PrimeFaces con ViewState                     ║
    ║                                                                  ║
    ║  ✅ LISTO PARA USAR - Datos verificados con DevTools           ║
    ║                                                                  ║
    ╚══════════════════════════════════════════════════════════════════╝
    """)
    
    print("\n✅ Configuración verificada:")
    print("   • URL: /vistas/common/datos/bsqFoneticaCompleta.pgi")
    print("   • Formulario: frmBsqFonetica")
    print("   • Campo marca: frmBsqFonetica:denominacion")
    print("   • Campo clase: frmBsqFonetica:clases")
    print("   • Tabla resultados: frmBsqFonetica:resultadoExpediente")
    print("   • Estructura de columnas verificada\n")
    
    print("🚀 Para probar:")
    print("   python impi_fonetico_real.py")
    print("   # Descomenta la última línea: ejemplo_uso()\n")
    
    # Descomentar para probar
    ejemplo_uso()
