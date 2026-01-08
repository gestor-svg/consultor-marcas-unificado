"""
Analizador de Viabilidad con Gemini
====================================

Analiza los resultados de búsqueda fonética del IMPI usando Gemini
para sugerir un porcentaje de viabilidad y generar recomendaciones.

Autor: Gestor SVG / MarcaSegura
Fecha: Enero 2026
"""

import google.generativeai as genai
from typing import Dict, List, Optional, Tuple
import logging
import json
from datetime import datetime

from impi_fonetico_COMPLETO import ResultadoBusqueda, MarcaInfo

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ConfigGemini:
    """Configuración de Gemini"""
    
    # API Key debe venir de variable de entorno
    import os
    API_KEY = os.getenv('API_KEY_GEMINI')
    MODEL = "gemini-1.5-flash"
    
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
        
        # Configurar Gemini
        api_key = api_key or self.config.API_KEY
        genai.configure(api_key=api_key)
        
        # Configurar modelo
        generation_config = {
            "temperature": self.config.TEMPERATURE,
            "top_p": self.config.TOP_P,
            "top_k": self.config.TOP_K,
            "max_output_tokens": self.config.MAX_OUTPUT_TOKENS,
        }
        
        self.model = genai.GenerativeModel(
            model_name=self.config.MODEL,
            generation_config=generation_config
        )
        
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
            
            # Llamar a Gemini
            response = self.model.generate_content(prompt)
            
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
        Genera el prompt para Gemini
        """
        
        # Información básica
        prompt = f"""Eres un experto en derecho de propiedad intelectual y marcas en México. Tu trabajo es analizar la viabilidad de registro de una marca ante el IMPI (Instituto Mexicano de la Propiedad Industrial).

**MARCA A ANALIZAR:**
Denominación: {resultado.marca_consultada}
Clase Niza: {resultado.clase_consultada if resultado.clase_consultada else "No especificada (todas las clases)"}
"""
        
        # Agregar descripción si existe
        if descripcion_producto:
            prompt += f"Descripción del producto/servicio: {descripcion_producto}\n"
        
        prompt += f"""
**RESULTADOS DE BÚSQUEDA FONÉTICA:**
Total de marcas similares encontradas: {resultado.total_registros}
Marcas parseadas y analizables: {len(resultado.marcas_encontradas)}

"""
        
        # Agregar detalles de marcas similares
        if resultado.marcas_encontradas:
            prompt += "**MARCAS SIMILARES DETECTADAS:**\n\n"
            
            for i, marca in enumerate(resultado.marcas_encontradas[:15], 1):
                prompt += f"{i}. {marca.denominacion}\n"
                prompt += f"   - Expediente: {marca.expediente}\n"
                prompt += f"   - Titular: {marca.titular}\n"
                prompt += f"   - Clase: {marca.clase}\n"
                prompt += f"   - Registro: {marca.fecha_registro}\n"
                prompt += "\n"
            
            if len(resultado.marcas_encontradas) > 15:
                prompt += f"... y {len(resultado.marcas_encontradas) - 15} marcas más.\n\n"
        else:
            prompt += "**No se encontraron marcas similares en la búsqueda.**\n\n"
        
        # Instrucciones de análisis
        prompt += """
**TU TAREA:**

Analiza estos resultados y proporciona tu respuesta en el siguiente formato JSON EXACTO (sin texto adicional, solo el JSON):

```json
{
  "porcentaje_viabilidad": <número entre 0 y 85>,
  "nivel_riesgo": "<BAJO|MEDIO|ALTO|MUY_ALTO>",
  "marcas_conflictivas": [
    {
      "denominacion": "<nombre de la marca conflictiva>",
      "expediente": "<número>",
      "razon_conflicto": "<por qué es conflictiva>",
      "nivel_conflicto": "<BAJO|MEDIO|ALTO>"
    }
  ],
  "analisis_detallado": "<análisis profesional en 2-3 párrafos explicando tu evaluación>",
  "recomendaciones": [
    "<recomendación 1>",
    "<recomendación 2>",
    "<recomendación 3>"
  ],
  "factores_riesgo": [
    "<factor de riesgo 1>",
    "<factor de riesgo 2>"
  ],
  "factores_favorables": [
    "<factor favorable 1>",
    "<factor favorable 2>"
  ]
}
```

**CRITERIOS DE EVALUACIÓN:**

1. **Similitud fonética:** ¿Qué tan similar suena la marca consultada con las existentes?
2. **Similitud visual:** ¿Qué tan parecidas se escriben?
3. **Misma clase de Niza:** Marcas en la misma clase son más conflictivas
4. **Cantidad de similares:** Más marcas similares = menor viabilidad
5. **Titulares:** Si el mismo titular tiene varias similares, puede ser estrategia de defensa
6. **Distintividad:** ¿La marca tiene elementos distintivos suficientes?

**ESCALA DE VIABILIDAD:**
- 0-25%: Muy pocas posibilidades (no recomendado)
- 26-50%: Pocas posibilidades (riesgoso)
- 51-65%: Posible con modificaciones (considerar cambios)
- 66-85%: Buena posibilidad (recomendado)

**IMPORTANTE:**
- NUNCA des 100% de viabilidad (máximo 85%)
- Sé conservador pero realista
- Considera que el revisor del IMPI tiene la decisión final
- Si no hay marcas similares, la viabilidad es alta (70-85%)
- Si hay 1-3 marcas similares pero en clases diferentes, viabilidad media-alta (60-75%)
- Si hay muchas marcas similares en la misma clase, viabilidad baja (20-50%)

Responde SOLO con el JSON, sin texto adicional antes o después.
"""
        
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
            
            # Crear análisis
            analisis = AnalisisViabilidad(
                marca_consultada=resultado.marca_consultada,
                clase_consultada=resultado.clase_consultada,
                porcentaje_viabilidad=porcentaje,
                nivel_riesgo=data.get('nivel_riesgo', 'MEDIO'),
                marcas_conflictivas=data.get('marcas_conflictivas', []),
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
