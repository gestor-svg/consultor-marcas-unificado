"""
Configuración del Sistema Interno - Consultor de Marcas
========================================================

Variables de configuración, usuarios autorizados, etc.
"""

import os
from datetime import timedelta

class Config:
    """Configuración base de la aplicación"""
    
    # Flask
    SECRET_KEY = os.getenv('SECRET_KEY', 'marcasegura-interna-secret-2025-super-secure')
    FLASK_ENV = os.getenv('FLASK_ENV', 'development')
    DEBUG = FLASK_ENV == 'development'
    
    # Sesión
    SESSION_COOKIE_NAME = 'marcasegura_session'
    SESSION_COOKIE_SECURE = FLASK_ENV == 'production'  # Solo HTTPS en producción
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    PERMANENT_SESSION_LIFETIME = timedelta(hours=12)  # Sesión expira en 12 horas
    
    # Usuarios autorizados
    # En producción, estos deberían venir de variables de entorno
    USUARIOS_AUTORIZADOS = {
        os.getenv('ADMIN_USER', 'gestor'): os.getenv('ADMIN_PASS', 'marcasegura2025'),
        'admin': os.getenv('ADMIN_PASS_2', 'admin_pass_2025')
    }
    
    # Google Sheets
    GOOGLE_SHEET_ID = '1uzaz2r10XwLRu-6iY0lyKQJCVVHkKMCbob-MqjAQ8Zc'
    GOOGLE_APPS_SCRIPT_URL = os.getenv(
        'GOOGLE_APPS_SCRIPT_URL',
        'https://script.google.com/macros/s/AKfycbzYOUR_SCRIPT_ID/exec'
    )
    HOJA_LEADS = 'leads'
    
    # Gemini AI
    GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
    
    # Email (opcional para envío automático)
    SMTP_HOST = os.getenv('SMTP_HOST', 'smtp.gmail.com')
    SMTP_PORT = int(os.getenv('SMTP_PORT', '587'))
    SMTP_USER = os.getenv('SMTP_USER', 'gestor@marcasegura.com.mx')
    SMTP_PASS = os.getenv('SMTP_PASS', '')
    EMAIL_FROM = os.getenv('EMAIL_FROM', 'gestor@marcasegura.com.mx')
    
    # Notificaciones ntfy.sh
    NTFY_CHANNEL = os.getenv('NTFY_CHANNEL', 'marcasegura-leads-2025')
    NTFY_ENABLED = os.getenv('NTFY_ENABLED', 'false').lower() == 'true'
    
    # PDFs
    PDF_FOLDER = os.path.join(os.path.dirname(__file__), 'pdfs')
    PDF_LOGO_PATH = os.path.join(os.path.dirname(__file__), 'static', 'img', 'logo_marcasegura.png')
    
    # Límites y configuraciones
    MAX_LEADS_POR_PAGINA = 50
    TIMEZONE = 'America/Mexico_City'
    
    # URLs
    URL_VERSION_PUBLICA = 'https://consultor-marcas-publica.onrender.com'
    URL_VERSION_INTERNA = os.getenv('URL_VERSION_INTERNA', 'http://localhost:5000')
    
    # Contacto
    WHATSAPP = '523331562224'
    EMAIL_CONTACTO = 'gestor@marcasegura.com.mx'
    NOMBRE_EMPRESA = 'MarcaSegura'


# Crear carpeta de PDFs si no existe
os.makedirs(Config.PDF_FOLDER, exist_ok=True)
