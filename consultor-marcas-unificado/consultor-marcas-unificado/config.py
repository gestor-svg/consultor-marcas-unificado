"""
Configuración del Sistema Unificado - Consultor de Marcas
==========================================================

Configuración para:
- Sistema PÚBLICO: Landing page, formulario, funnel de ventas
- Sistema INTERNO: Dashboard de expertos, análisis, PDFs

Variables de configuración, usuarios autorizados, etc.
"""

import os
from datetime import timedelta
import pytz

class Config:
    """Configuración base de la aplicación unificada"""
    
    # ============================================
    # CONFIGURACIÓN GENERAL (COMPARTIDA)
    # ============================================
    
    # Flask
    SECRET_KEY = os.getenv('SECRET_KEY', 'marcasegura-unificado-secret-2025-super-secure')
    FLASK_ENV = os.getenv('FLASK_ENV', 'development')
    DEBUG = FLASK_ENV == 'development'
    
    # Sesión
    SESSION_COOKIE_NAME = 'marcasegura_session'
    SESSION_COOKIE_SECURE = FLASK_ENV == 'production'  # Solo HTTPS en producción
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    PERMANENT_SESSION_LIFETIME = timedelta(hours=12)  # Sesión expira en 12 horas
    
    # Zona horaria de México
    TIMEZONE = 'America/Mexico_City'
    MEXICO_TZ = pytz.timezone('America/Mexico_City')
    
    # Google Sheets (COMPARTIDO - Sistema de IDs único)
    GOOGLE_SHEET_ID = '1uzaz2r10XwLRu-6iY0lyKQJCVVHkKMCbob-MqjAQ8Zc'
    GOOGLE_APPS_SCRIPT_URL = os.getenv(
        'GOOGLE_APPS_SCRIPT_URL',
        'https://script.google.com/macros/s/AKfycbxGeRx724y1DudHGhf783PJjPtRA8-M8_34-IZ1yvi-N_-M_Es7NXFgdu5IGmt2rs_VhA/exec'
    )
    HOJA_LEADS = 'leads'
    
    # Gemini AI (COMPARTIDO)
    GEMINI_API_KEY = os.getenv('API_KEY_GEMINI')
    
    # Email (COMPARTIDO)
    SMTP_HOST = os.getenv('SMTP_HOST', 'smtp.gmail.com')
    SMTP_PORT = int(os.getenv('SMTP_PORT', '587'))
    GMAIL_USER = os.getenv('GMAIL_USER', 'gestor@marcasegura.com.mx')
    GMAIL_PASSWORD = os.getenv('GMAIL_PASSWORD', '')
    SMTP_USER = os.getenv('SMTP_USER', 'gestor@marcasegura.com.mx')
    SMTP_PASS = os.getenv('SMTP_PASS', '')
    EMAIL_FROM = os.getenv('EMAIL_FROM', 'gestor@marcasegura.com.mx')
    EMAIL_DESTINO = 'gestor@marcasegura.com.mx'
    
    # Notificaciones ntfy.sh (COMPARTIDO)
    NTFY_CHANNEL = os.getenv('NTFY_CHANNEL', 'marcasegura-leads-2025')
    NTFY_ENABLED = os.getenv('NTFY_ENABLED', 'true').lower() == 'true'
    
    # Contacto (COMPARTIDO)
    WHATSAPP_NUMERO = os.getenv('WHATSAPP_NUMERO', '523331562224')
    EMAIL_CONTACTO = 'gestor@marcasegura.com.mx'
    NOMBRE_EMPRESA = 'MarcaSegura'
    
    # ============================================
    # CONFIGURACIÓN PÚBLICA (FUNNEL DE VENTAS)
    # ============================================
    
    # Precios y pagos
    PRECIO_REPORTE = 950  # MXN
    MERCADO_PAGO_LINK = os.getenv('MERCADO_PAGO_LINK', 'https://mpago.li/2xfRia')
    
    # Integraciones externas
    CAL_COM_URL = os.getenv('CAL_COM_URL', 'https://cal.com/marcasegura/30min')
    APP_BASE_URL = os.getenv('APP_BASE_URL', 'https://consultor-marcas-unificado.onrender.com')
    
    # Debug
    DEBUG_IMPI = os.getenv('DEBUG_IMPI', 'false').lower() == 'true'
    
    # ============================================
    # CONFIGURACIÓN INTERNA (DASHBOARD EXPERTOS)
    # ============================================
    
    # Usuarios autorizados (Sistema Interno)
    # En producción, estos deberían venir de variables de entorno
    USUARIOS_AUTORIZADOS = {
        os.getenv('ADMIN_USER', 'gestor'): os.getenv('ADMIN_PASS', 'marcasegura2025'),
        'admin': os.getenv('ADMIN_PASS_2', 'admin_pass_2025')
    }
    
    # PDFs (Sistema Interno)
    PDF_FOLDER = os.path.join(os.path.dirname(__file__), 'pdfs')
    PDF_LOGO_PATH = os.path.join(os.path.dirname(__file__), 'static', 'internal', 'img', 'logo_marcasegura.png')
    
    # Límites y configuraciones (Sistema Interno)
    MAX_LEADS_POR_PAGINA = 50
    
    # URLs internas
    URL_VERSION_INTERNA = os.getenv('URL_VERSION_INTERNA', 'http://localhost:5000')


# Crear carpeta de PDFs si no existe
os.makedirs(Config.PDF_FOLDER, exist_ok=True)
