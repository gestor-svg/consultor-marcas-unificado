"""
Utilidades para el Funnel Público
==================================

Funciones auxiliares para:
- Clasificación con Gemini
- Notificaciones push (ntfy.sh)
- Mensajes de WhatsApp
- Emails
- Clases de Niza

Autor: Gestor SVG / MarcaSegura
Fecha: Enero 2026
"""

import requests
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from urllib.parse import quote
import re
import logging
from functools import lru_cache

try:
    import google.generativeai as genai
except ImportError:
    genai = None

logger = logging.getLogger(__name__)

# Diccionario completo de Clases de Niza
CLASES_NIZA = {
    "1": "Productos químicos",
    "2": "Pinturas y barnices",
    "3": "Cosméticos y productos de limpieza",
    "4": "Lubricantes y combustibles",
    "5": "Productos farmacéuticos",
    "6": "Metales comunes y sus aleaciones",
    "7": "Máquinas y máquinas herramientas",
    "8": "Herramientas e instrumentos de mano",
    "9": "Aparatos e instrumentos científicos y electrónicos",
    "10": "Aparatos e instrumentos médicos",
    "11": "Aparatos de iluminación, calefacción y cocción",
    "12": "Vehículos y medios de transporte",
    "13": "Armas de fuego y pirotecnia",
    "14": "Joyería y relojería",
    "15": "Instrumentos musicales",
    "16": "Papel, cartón y artículos de oficina",
    "17": "Caucho, plásticos y materiales aislantes",
    "18": "Cuero, equipaje y artículos de viaje",
    "19": "Materiales de construcción no metálicos",
    "20": "Muebles y artículos de madera",
    "21": "Utensilios de cocina y recipientes",
    "22": "Cuerdas, lonas y materiales textiles",
    "23": "Hilos para uso textil",
    "24": "Tejidos y cubiertas textiles",
    "25": "Prendas de vestir, calzado y sombreros",
    "26": "Artículos de mercería y pasamanería",
    "27": "Alfombras y revestimientos de suelos",
    "28": "Juegos, juguetes y artículos deportivos",
    "29": "Carne, pescado, frutas y verduras procesadas",
    "30": "Café, té, cacao, pan y pastelería",
    "31": "Productos agrícolas y forestales",
    "32": "Cervezas, bebidas sin alcohol y aguas",
    "33": "Bebidas alcohólicas (excepto cervezas)",
    "34": "Tabaco y artículos para fumadores",
    "35": "Publicidad y gestión de negocios",
    "36": "Servicios financieros y de seguros",
    "37": "Servicios de construcción y reparación",
    "38": "Servicios de telecomunicaciones",
    "39": "Servicios de transporte y almacenamiento",
    "40": "Tratamiento de materiales",
    "41": "Educación, formación y entretenimiento",
    "42": "Servicios científicos y tecnológicos",
    "43": "Servicios de restauración y hospedaje",
    "44": "Servicios médicos y de belleza",
    "45": "Servicios jurídicos y de seguridad",
}


def obtener_nombre_clase(numero_clase):
    """Obtiene el nombre descriptivo de una clase de Niza"""
    return CLASES_NIZA.get(str(numero_clase), f"Clase {numero_clase}")


@lru_cache(maxsize=100)
def clasificar_con_gemini(descripcion, tipo_negocio, api_key):
    """Usa Gemini para determinar la clase de Niza"""
    if not api_key or not genai:
        return {
            "clase_principal": "35",
            "clase_nombre": obtener_nombre_clase("35"),
            "clases_adicionales": [],
            "nota": "IA no disponible"
        }
    
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-2.0-flash-exp')
        
        prompt = f"""Eres un experto en clasificación de marcas según el sistema de Niza.

Clasifica este negocio: "{descripcion}" (Tipo: {tipo_negocio})

INSTRUCCIONES:
- Responde ÚNICAMENTE con el formato: NÚMERO|NOMBRE_CLASE|NOTA_BREVE
- El NÚMERO debe ser entre 1 y 45
- No incluyas explicaciones adicionales

EJEMPLOS DE RESPUESTA CORRECTA:
45|Servicios jurídicos|Registro de marcas y patentes
43|Restaurantes y cafeterías|Servicios de alimentación
25|Prendas de vestir|Ropa y calzado
9|Software y aplicaciones|Tecnología digital
35|Publicidad y negocios|Servicios comerciales

GUÍA RÁPIDA DE CLASES:
- Registro de marcas/patentes/propiedad intelectual = 45
- Servicios legales/abogados/notarios = 45
- Seguridad/vigilancia/investigación = 45
- Bebidas sin alcohol = 32
- Bebidas alcohólicas = 33
- Alimentos procesados = 29
- Pan, café, dulces = 30
- Restaurantes/cafeterías/hoteles = 43
- Ropa/calzado/sombreros = 25
- Software/apps/electrónicos = 9
- Desarrollo tecnológico/IT/programación = 42
- Publicidad/marketing/comercio/franquicias = 35
- Servicios médicos/clínicas/dentistas = 44
- Salones de belleza/spa/estética = 44
- Educación/capacitación/entretenimiento = 41
- Transporte/logística/almacenamiento = 39
- Construcción/reparación/instalación = 37
- Telecomunicaciones = 38
- Seguros/finanzas/bienes raíces = 36

Responde ahora:"""

        response = model.generate_content(
            prompt,
            generation_config=genai.GenerationConfig(
                temperature=0.1,
                max_output_tokens=100,
            )
        )
        
        text = response.text.strip()
        logger.info(f"[GEMINI] Respuesta: {text}")
        
        # Limpiar respuesta
        text = text.replace('```', '').strip()
        
        if '|' in text:
            partes = text.split('|')
            if len(partes) >= 2:
                clase = partes[0].strip()
                nombre = partes[1].strip() if len(partes) > 1 else ""
                nota = partes[2].strip() if len(partes) > 2 else nombre
                
                match = re.search(r'\d+', clase)
                clase_num = match.group() if match else clase
                
                # Validar rango
                try:
                    clase_int = int(clase_num)
                    if clase_int < 1 or clase_int > 45:
                        raise ValueError("Clase fuera de rango")
                except:
                    clase_num = "35"
                    nombre = obtener_nombre_clase("35")
                
                return {
                    "clase_principal": clase_num,
                    "clase_nombre": nombre if nombre else obtener_nombre_clase(clase_num),
                    "clases_adicionales": [],
                    "nota": nota
                }
        
        # Fallback
        numeros = re.findall(r'\b\d{1,2}\b', text)
        if numeros:
            clase_num = numeros[0]
            if 1 <= int(clase_num) <= 45:
                return {
                    "clase_principal": clase_num,
                    "clase_nombre": obtener_nombre_clase(clase_num),
                    "clases_adicionales": [],
                    "nota": text[:100]
                }
        
        raise ValueError("No se pudo extraer clase")
        
    except Exception as e:
        logger.error(f"[GEMINI] Error: {e}")
        # Clasificación de respaldo
        if tipo_negocio.lower() == 'producto':
            if any(kw in descripcion.lower() for kw in ['bebida', 'refresco', 'agua', 'jugo']):
                return {"clase_principal": "32", "clase_nombre": obtener_nombre_clase("32"), "clases_adicionales": [], "nota": "Clasificación automática"}
            elif any(kw in descripcion.lower() for kw in ['comida', 'alimento', 'snack']):
                return {"clase_principal": "29", "clase_nombre": obtener_nombre_clase("29"), "clases_adicionales": [], "nota": "Clasificación automática"}
            elif any(kw in descripcion.lower() for kw in ['ropa', 'vestido', 'calzado']):
                return {"clase_principal": "25", "clase_nombre": obtener_nombre_clase("25"), "clases_adicionales": [], "nota": "Clasificación automática"}
            return {"clase_principal": "1", "clase_nombre": obtener_nombre_clase("1"), "clases_adicionales": [], "nota": "Clasificación por defecto"}
        else:
            if any(kw in descripcion.lower() for kw in ['restaurante', 'cafetería', 'bar', 'comida', 'café']):
                return {"clase_principal": "43", "clase_nombre": obtener_nombre_clase("43"), "clases_adicionales": [], "nota": "Clasificación automática"}
            elif any(kw in descripcion.lower() for kw in ['software', 'desarrollo', 'tecnolog', 'it', 'sistemas']):
                return {"clase_principal": "42", "clase_nombre": obtener_nombre_clase("42"), "clases_adicionales": [], "nota": "Clasificación automática"}
            return {"clase_principal": "35", "clase_nombre": obtener_nombre_clase("35"), "clases_adicionales": [], "nota": "Clasificación por defecto"}


def enviar_notificacion_push(datos_lead, ntfy_channel, app_url):
    """Envía notificación push via ntfy.sh"""
    try:
        titulo = f"Nuevo Lead: {datos_lead.get('nombre', 'Sin nombre')}"
        mensaje = f"""Tel: {datos_lead.get('telefono', 'N/A')}
Email: {datos_lead.get('email', 'N/A')}
Marca: {datos_lead.get('marca', 'N/A')}
Tipo: {datos_lead.get('tipo_negocio', 'N/A')}
Clase: {datos_lead.get('clase_sugerida', 'N/A')}
Status: {datos_lead.get('status_impi', 'N/A')}"""

        response = requests.post(
            f"https://ntfy.sh/{ntfy_channel}",
            data=mensaje.encode('utf-8'),
            headers={
                "Title": titulo.encode('utf-8'),
                "Priority": "high",
                "Tags": "briefcase,dollar",
                "Icon": f"{app_url}/static/public/logo.png"
            },
            timeout=10
        )
        
        if response.status_code == 200:
            logger.info(f"[PUSH] Notificación enviada")
            return True
        else:
            logger.error(f"[PUSH] Error: {response.status_code}")
            return False
    except Exception as e:
        logger.error(f"[PUSH] Error: {e}")
        return False


def enviar_email_lead(datos_lead, gmail_user, gmail_password, email_destino, mexico_tz):
    """Envía email de notificación de lead"""
    if not gmail_user or not gmail_password:
        logger.warning("[EMAIL] No configurado")
        return False
    
    try:
        texto = f"""
NUEVO LEAD - CONSULTOR DE MARCAS

Nombre: {datos_lead.get('nombre', 'N/A')}
Email: {datos_lead.get('email', 'N/A')}
Teléfono: {datos_lead.get('telefono', 'N/A')}

Marca: {datos_lead.get('marca', 'N/A')}
Status: {datos_lead.get('status_impi', 'N/A')}
Clase: {datos_lead.get('clase_sugerida', 'N/A')}

Fecha: {datetime.now(mexico_tz).strftime('%Y-%m-%d %H:%M')}
        """
        
        mensaje = MIMEText(texto, 'plain', 'utf-8')
        mensaje['Subject'] = f"Lead - {datos_lead.get('nombre', 'Cliente')} | {datos_lead.get('marca', 'Marca')}"
        mensaje['From'] = gmail_user
        mensaje['To'] = email_destino
        
        with smtplib.SMTP('smtp.gmail.com', 587, timeout=10) as servidor:
            servidor.starttls()
            servidor.login(gmail_user, gmail_password)
            servidor.send_message(mensaje)
        
        logger.info(f"[EMAIL] Enviado")
        return True
    except Exception as e:
        logger.error(f"[EMAIL] Error: {e}")
        return False


def generar_whatsapp_lead_nuevo(datos_lead, whatsapp_numero, mexico_tz):
    """Genera URL de WhatsApp para lead nuevo"""
    mensaje = f"""🆕 *NUEVO LEAD CAPTURADO*

📋 *Datos:*
• Nombre: {datos_lead.get('nombre', 'N/A')}
• Email: {datos_lead.get('email', 'N/A')}
• Teléfono: {datos_lead.get('telefono', 'N/A')}

🏷️ *Consulta:*
• Marca: {datos_lead.get('marca', 'N/A')}
• Tipo: {datos_lead.get('tipo_negocio', 'N/A')}
• Clase: {datos_lead.get('clase_sugerida', 'N/A')}
• Status: {datos_lead.get('status_impi', 'N/A')}

📅 {datetime.now(mexico_tz).strftime('%Y-%m-%d %H:%M')}
⏳ Pendiente de pago

💡 Seguimiento recomendado en 24-48 hrs si no compra.
"""
    return f"https://wa.me/{whatsapp_numero}?text={quote(mensaje)}"
