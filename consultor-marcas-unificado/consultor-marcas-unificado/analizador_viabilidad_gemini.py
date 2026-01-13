"""
Analizador de Viabilidad con Gemini
====================================

Analiza los resultados de búsqueda fonética del IMPI usando Gemini
para sugerir un porcentaje de viabilidad y generar recomendaciones.

Autor: Gestor SVG / MarcaSegura
Fecha: Enero 2026
"""

from google.genai import Client
from google.genai.types import GenerateContentConfig
from typing import Dict, List, Optional, Tuple
import logging
import json
from datetime import datetime
import os

from impi_fonetico_COMPLETO import ResultadoBusqueda, MarcaInfo

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ConfigGemini:
    """Configuración de Gemini"""
    
    # API Key debe venir de variable de entorno
    API_KEY = os.getenv('GEMINI_API_KEY')
    MODEL = "gemini-2.0-flash-exp"  # Modelo actualizado
    
    # Parámetros de generación
    TEMPERATURE = 0.7  # Creatividad moderada
    TOP_P = 0.9
    TOP_K = 40
    MAX_OUTPUT_TOKENS = 2048
    
    # Escala de viabilidad
    VIABILIDAD_MIN = 0
    VIABILIDAD_MAX = 85  # Nunca 100% por factor humano del revisor IMPI


class AnalisisViabilidad:
    """
    Modelo de datos para el análisis de viabilidad
    """
    
    def __init__(
        self,
        marca_consultada: str,
        clase_consultada: Optional[int],
        porcentaje_viabilidad: int,
        nivel_riesgo: str,
        marcas_conflictivas: List[Dict],
        analisis_detallado: str,
        recomendaciones: List[str],
        factores_riesgo: List[str],
        factores_favorables: List[str],
        fecha_analisis: datetime
    ):
        self.marca_consultada = marca_consultada
        self.clase_consultada = clase_consultada
        self.porcentaje_viabilidad = porcentaje_viabilidad
        self.nivel_riesgo = nivel_riesgo
        self.marcas_conflictivas = marcas_conflictivas
        self.analisis_detallado = analisis_detallado
        self.recomendaciones = recomendaciones
        self.factores_riesgo = factores_riesgo
        self.factores_favorables = factores_favorables
        self.fecha_analisis = fecha_analisis
    
    def to_dict(self) -> Dict:
        """Convierte el análisis a diccionario"""
        return {
            'marca_consultada': self.marca_consultada,
            'clase_consultada': self.clase_consultada,
            'porcentaje_viabilidad': self.porcentaje_viabilidad,
            'nivel_riesgo': self.nivel_riesgo,
            'marcas_conflictivas': self.marcas_conflictivas,
            'analisis_detallado': self.analisis_detallado,
            'recomendaciones': self.recomendaciones,
            'factores_riesgo': self.factores_riesgo,
            'factores_favorables': self.factores_favorables,
            'fecha_analisis': self.fecha_analisis.isoformat()
        }


class AnalizadorViabilidadGemini:
    """
    Analizador de viabilidad de marcas usando Gemini
    """
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Inicializa el analizador
        
        Args:
            api_key: API key de Gemini (opcional, usa la de ConfigGemini por defecto)
        """
        self.config = ConfigGemini()
        
        # Configurar Gemini con nueva API
        api_key = api_key or self.config.API_KEY
        
        if not api_key:
            raise ValueError("API key de Gemini no configurada. Verifica GEMINI_API_KEY en variables de entorno.")
        
        # Crear cliente con nueva API
        self.client = Client(api_key=api_key)
        
        logger.info(f"✅ Analizador Gemini inicializado con modelo {self.config.MODEL}")
    
    def analizar_viabilidad(
        self,
        resultado_busqueda: ResultadoBusqueda,
        descripcion_producto: Optional[str] = None
    ) -> AnalisisViabilidad:
        """
        Analiza la viabilidad de registro de una marca
        
        Args:
            resultado_busqueda: Resultado de la búsqueda fonética IMPI
            descripcion_producto: Descripción del producto/servicio (opcional)
        
        Returns:
            AnalisisViabilidad con el análisis completo
        """
        
        if not resultado_busqueda.exito:
            logger.error(f"No se puede analizar búsqueda fallida: {resultado_busqueda.error}")
            return self._analisis_error(resultado_busqueda, resultado_busqueda.error)
        
        logger.info(f"🤖 Analizando viabilidad de '{resultado_busqueda.marca_consultada}'...")
        
        try:
            # Generar prompt
            prompt = self._generar_prompt_analisis(
                resultado_busqueda,
                descripcion_producto
            )
            
            logger.debug(f"Prompt generado: {len(prompt)} caracteres")
            
            # Llamar a Gemini con nueva API
            response = self.client.models.generate_content(
                model=self.config.MODEL,
                contents=prompt,
                config=GenerateContentConfig(
                    temperature=self.config.TEMPERATURE,
                    top_p=self.config.TOP_P,
                    top_k=self.config.TOP_K,
                    max_output_tokens=self.config.MAX_OUTPUT_TOKENS
                )
            )
            
            if not response or not response.text:
                logger.error("Gemini no devolvió respuesta")
                return self._analisis_error(resultado_busqueda, "Sin respuesta de Gemini")
            
            logger.debug(f"Respuesta de Gemini: {len(response.text)} caracteres")
            
            # Parsear respuesta
            analisis = self._parsear_respuesta_gemini(
                response.text,
                resultado_busqueda
            )
            
            logger.info(f"✅ Análisis completado: {analisis.porcentaje_viabilidad}% viabilidad")
            
            return analisis
        
        except Exception as e:
            logger.error(f"Error en análisis: {str(e)}", exc_info=True)
            return self._analisis_error(resultado_busqueda, str(e))
    
    def _generar_prompt_analisis(
        self,
        resultado: ResultadoBusqueda,
        descripcion_producto: Optional[str]
    ) -> str:
        """
        Genera el prompt para Gemini - versión con análisis inteligente
        """
        
        total_marcas = len(resultado.marcas_encontradas)
        
        # Información básica
        prompt = f"""Eres un experto en derecho de propiedad intelectual y marcas en México. Analizas la viabilidad de registro de marcas ante el IMPI.

**MARCA A ANALIZAR:**
Denominación: "{resultado.marca_consultada}"
Clase Niza: {resultado.clase_consultada if resultado.clase_consultada else "Todas las clases"}
"""
        
        if descripcion_producto:
            prompt += f"Descripción: {descripcion_producto}\n"
        
        prompt += f"""
**RESULTADOS BÚSQUEDA FONÉTICA IMPI:**
Se encontraron {total_marcas} marcas similares registradas o en trámite.

**TODAS LAS MARCAS ({total_marcas} total):**
"""
        
        # Listar TODAS las marcas para que Gemini las analice
        for i, marca in enumerate(resultado.marcas_encontradas, 1):
            prompt += f"\n{i}. {marca.denominacion}"
            prompt += f"\n   Expediente: {marca.expediente}"
            if marca.registro:
                prompt += f" | Registro: {marca.registro}"
            prompt += f" | Clase: {marca.clase}"
            prompt += f" | Titular: {marca.titular[:50]}..."
        
        # Instrucciones críticas
        prompt += f"""

**TU TAREA CRÍTICA:**

1. **IDENTIFICA** las 15 marcas MÁS CONFLICTIVAS de las {total_marcas} analizadas
2. **ORDÉNALAS** por nivel de riesgo (más peligrosa primero)
3. **PRIORIZA**:
   - Coincidencias EXACTAS (ej: "CAFE LUNA" vs "LUNA CAFE") → RIESGO MUY ALTO
   - Marcas con REGISTRO vigente (no solo expediente) → MÁS PELIGROSAS
   - Alta similitud fonética en misma clase → RIESGO ALTO
   - Similitud moderada → RIESGO MEDIO

4. **CALCULA** viabilidad considerando TODAS las {total_marcas} marcas:
   - Coincidencia exacta con registro → 15-25%
   - Similitudes altas múltiples → 30-45%
   - Similitudes moderadas → 50-65%
   - Solo similitudes bajas → 70-80%

**RESPONDE EN FORMATO JSON EXACTO (sin markdown, solo JSON):**

{{
  "porcentaje_viabilidad": <número 15-80>,
  "nivel_riesgo": "<MUY_ALTO|ALTO|MEDIO|BAJO>",
  "top_15_conflictivas": [
    {{
      "posicion": 1,
      "denominacion": "<nombre exacto>",
      "expediente": "<número>",
      "registro": "<número o vacío>",
      "razon_conflicto": "<explicación breve>",
      "nivel_conflicto": "<MUY_ALTO|ALTO|MEDIO|BAJO>"
    }}
  ],
  "analisis_detallado": "<2-3 párrafos explicando: 1) Por qué ese porcentaje, 2) Marcas más peligrosas, 3) Consideraciones>",
  "recomendaciones": [
    "<acción concreta 1>",
    "<acción concreta 2>",
    "<acción concreta 3>"
  ],
  "factores_riesgo": ["<factor 1>", "<factor 2>"],
  "factores_favorables": ["<factor 1>", "<factor 2>"],
  "total_marcas_analizadas": {total_marcas}
}}

IMPORTANTE: Las "top_15_conflictivas" deben estar ORDENADAS por riesgo descendente (más peligrosa primero)."""
        
        return prompt
    
    def _parsear_respuesta_gemini(
        self,
        respuesta_texto: str,
        resultado: ResultadoBusqueda
    ) -> AnalisisViabilidad:
        """
        Parsea la respuesta JSON de Gemini
        """
        
        try:
            # Limpiar respuesta (remover markdown si existe)
            texto = respuesta_texto.strip()
            
            # Remover ```json y ``` si existen
            if texto.startswith("```json"):
                texto = texto[7:]
            if texto.startswith("```"):
                texto = texto[3:]
            if texto.endswith("```"):
                texto = texto[:-3]
            
            texto = texto.strip()
            
            # Parsear JSON
            data = json.loads(texto)
            
            # Validar porcentaje
            porcentaje = int(data.get('porcentaje_viabilidad', 50))
            porcentaje = max(self.config.VIABILIDAD_MIN, min(porcentaje, self.config.VIABILIDAD_MAX))
            
            # Obtener marcas conflictivas (usar el nuevo campo o el viejo para compatibilidad)
            marcas_conflictivas = data.get('top_15_conflictivas', data.get('marcas_conflictivas', []))
            
            # Crear análisis
            analisis = AnalisisViabilidad(
                marca_consultada=resultado.marca_consultada,
                clase_consultada=resultado.clase_consultada,
                porcentaje_viabilidad=porcentaje,
                nivel_riesgo=data.get('nivel_riesgo', 'MEDIO'),
                marcas_conflictivas=marcas_conflictivas,
                analisis_detallado=data.get('analisis_detallado', ''),
                recomendaciones=data.get('recomendaciones', []),
                factores_riesgo=data.get('factores_riesgo', []),
                factores_favorables=data.get('factores_favorables', []),
                fecha_analisis=datetime.now()
            )
            
            return analisis
        
        except json.JSONDecodeError as e:
            logger.error(f"Error parseando JSON de Gemini: {str(e)}")
            logger.debug(f"Respuesta: {respuesta_texto}")
            
            # Fallback: análisis básico
            return self._analisis_fallback(resultado, respuesta_texto)
        
        except Exception as e:
            logger.error(f"Error procesando respuesta: {str(e)}")
            return self._analisis_fallback(resultado, respuesta_texto)
    
    def _analisis_fallback(
        self,
        resultado: ResultadoBusqueda,
        respuesta_texto: str
    ) -> AnalisisViabilidad:
        """
        Crea un análisis básico cuando falla el parseo JSON
        """
        
        total = resultado.total_registros
        
        # Lógica simple de viabilidad
        if total == 0:
            porcentaje = 75
            nivel = "BAJO"
        elif total <= 3:
            porcentaje = 60
            nivel = "MEDIO"
        elif total <= 10:
            porcentaje = 40
            nivel = "ALTO"
        else:
            porcentaje = 25
            nivel = "MUY_ALTO"
        
        return AnalisisViabilidad(
            marca_consultada=resultado.marca_consultada,
            clase_consultada=resultado.clase_consultada,
            porcentaje_viabilidad=porcentaje,
            nivel_riesgo=nivel,
            marcas_conflictivas=[],
            analisis_detallado=respuesta_texto if respuesta_texto else "Análisis automático basado en cantidad de marcas similares.",
            recomendaciones=[
                "Revisar manualmente las marcas similares encontradas",
                "Considerar modificar la denominación si hay conflictos",
                "Consultar con un experto en propiedad intelectual"
            ],
            factores_riesgo=[f"Se encontraron {total} marcas similares"],
            factores_favorables=[] if total > 0 else ["No se encontraron marcas similares"],
            fecha_analisis=datetime.now()
        )
    
    def _analisis_error(
        self,
        resultado: ResultadoBusqueda,
        error: str
    ) -> AnalisisViabilidad:
        """
        Crea un análisis de error
        """
        
        return AnalisisViabilidad(
            marca_consultada=resultado.marca_consultada,
            clase_consultada=resultado.clase_consultada,
            porcentaje_viabilidad=0,
            nivel_riesgo="ERROR",
            marcas_conflictivas=[],
            analisis_detallado=f"No se pudo completar el análisis: {error}",
            recomendaciones=["Intentar nuevamente la búsqueda"],
            factores_riesgo=[f"Error: {error}"],
            factores_favorables=[],
            fecha_analisis=datetime.now()
        )


# =============================================================================
# FUNCIONES DE UTILIDAD
# =============================================================================

def clasificar_viabilidad(porcentaje: int) -> Tuple[str, str]:
    """
    Clasifica el porcentaje de viabilidad en categorías
    
    Returns:
        Tuple de (categoría, descripción)
    """
    
    if porcentaje <= 25:
        return ("MUY_BAJA", "Muy pocas posibilidades - No recomendado registrar")
    elif porcentaje <= 50:
        return ("BAJA", "Pocas posibilidades - Riesgoso, considerar alternativas")
    elif porcentaje <= 65:
        return ("MEDIA", "Posible con cambios - Agregar slogan o modificar descripción")
    else:  # 66-85
        return ("ALTA", "Buena posibilidad - Recomendado para registro")


def generar_resumen_ejecutivo(analisis: AnalisisViabilidad) -> str:
    """
    Genera un resumen ejecutivo del análisis
    """
    
    categoria, descripcion = clasificar_viabilidad(analisis.porcentaje_viabilidad)
    
    resumen = f"""
RESUMEN EJECUTIVO - ANÁLISIS DE VIABILIDAD
{'='*60}

Marca: {analisis.marca_consultada}
Clase: {analisis.clase_consultada if analisis.clase_consultada else "No especificada"}

VIABILIDAD: {analisis.porcentaje_viabilidad}%
CATEGORÍA: {categoria}
NIVEL DE RIESGO: {analisis.nivel_riesgo}

{descripcion}

{'='*60}
"""
    
    return resumen


# =============================================================================
# EJEMPLO DE USO
# =============================================================================

def ejemplo_uso():
    """Ejemplo completo de búsqueda + análisis"""
    
    from impi_fonetico_COMPLETO import IMPIBuscadorFonetico
    
    print("="*70)
    print(" EJEMPLO: BÚSQUEDA + ANÁLISIS CON GEMINI")
    print("="*70)
    
    # 1. Búsqueda fonética
    print("\n🔍 Paso 1: Búsqueda fonética en IMPI...")
    buscador = IMPIBuscadorFonetico()
    resultado = buscador.buscar_fonetica("COCA COLA", clase_niza=32)
    
    if not resultado.exito:
        print(f"❌ Error en búsqueda: {resultado.error}")
        return
    
    print(f"✅ Búsqueda completada: {resultado.total_registros} marcas encontradas")
    
    # 2. Análisis con Gemini
    print("\n🤖 Paso 2: Análisis con Gemini...")
    analizador = AnalizadorViabilidadGemini()
    analisis = analizador.analizar_viabilidad(
        resultado,
        descripcion_producto="Bebida gaseosa con sabor a cola"
    )
    
    # 3. Mostrar resultados
    print("\n" + "="*70)
    print(generar_resumen_ejecutivo(analisis))
    
    print("\n📊 ANÁLISIS DETALLADO:")
    print("-" * 70)
    print(analisis.analisis_detallado)
    
    if analisis.marcas_conflictivas:
        print(f"\n⚠️ MARCAS CONFLICTIVAS ({len(analisis.marcas_conflictivas)}):")
        print("-" * 70)
        for marca in analisis.marcas_conflictivas[:5]:
            print(f"\n• {marca.get('denominacion', 'N/A')}")
            print(f"  Expediente: {marca.get('expediente', 'N/A')}")
            print(f"  Conflicto: {marca.get('razon_conflicto', 'N/A')}")
            print(f"  Nivel: {marca.get('nivel_conflicto', 'N/A')}")
    
    if analisis.factores_riesgo:
        print("\n⚠️ FACTORES DE RIESGO:")
        print("-" * 70)
        for factor in analisis.factores_riesgo:
            print(f"• {factor}")
    
    if analisis.factores_favorables:
        print("\n✅ FACTORES FAVORABLES:")
        print("-" * 70)
        for factor in analisis.factores_favorables:
            print(f"• {factor}")
    
    if analisis.recomendaciones:
        print("\n💡 RECOMENDACIONES:")
        print("-" * 70)
        for i, rec in enumerate(analisis.recomendaciones, 1):
            print(f"{i}. {rec}")
    
    # 4. Exportar a JSON
    print("\n\n📄 EXPORTAR A JSON:")
    print("-" * 70)
    print(json.dumps(analisis.to_dict(), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    print("""
    ╔══════════════════════════════════════════════════════════════════╗
    ║                                                                  ║
    ║     ANALIZADOR DE VIABILIDAD CON GEMINI                        ║
    ║     Integración completa con búsqueda fonética IMPI            ║
    ║                                                                  ║
    ║  ✅ API KEY configurada                                         ║
    ║  ✅ Modelo: gemini-pro                                          ║
    ║  ✅ Análisis automático de viabilidad                          ║
    ║                                                                  ║
    ╚══════════════════════════════════════════════════════════════════╝
    """)
    
    # Ejecutar ejemplo
    ejemplo_uso()
