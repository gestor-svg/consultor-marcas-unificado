"""
Autenticación y Seguridad
==========================

Sistema de login simple con protección de rutas.
"""

from functools import wraps
from flask import session, redirect, url_for, flash
import logging

logger = logging.getLogger(__name__)


def login_required(f):
    """
    Decorador para proteger rutas que requieren autenticación
    
    Uso:
        @app.route('/dashboard')
        @login_required
        def dashboard():
            return render_template('dashboard.html')
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'usuario' not in session:
            flash('Por favor inicia sesión para acceder', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


def verificar_credenciales(usuario: str, password: str, usuarios_autorizados: dict) -> bool:
    """
    Verifica si las credenciales son válidas
    
    Args:
        usuario: Nombre de usuario
        password: Contraseña
        usuarios_autorizados: Diccionario de usuarios autorizados
    
    Returns:
        True si las credenciales son válidas
    """
    
    if usuario not in usuarios_autorizados:
        logger.warning(f"🔒 Intento de login con usuario no autorizado: {usuario}")
        return False
    
    if usuarios_autorizados[usuario] != password:
        logger.warning(f"🔒 Intento de login con contraseña incorrecta: {usuario}")
        return False
    
    logger.info(f"✅ Login exitoso: {usuario}")
    return True


def iniciar_sesion(usuario: str) -> None:
    """
    Inicia sesión para un usuario
    
    Args:
        usuario: Nombre de usuario
    """
    session['usuario'] = usuario
    session.permanent = True  # Usar PERMANENT_SESSION_LIFETIME de config


def cerrar_sesion() -> None:
    """Cierra la sesión actual"""
    if 'usuario' in session:
        usuario = session['usuario']
        session.clear()
        logger.info(f"👋 Logout: {usuario}")
    else:
        session.clear()


def obtener_usuario_actual() -> str:
    """
    Obtiene el usuario actual de la sesión
    
    Returns:
        Nombre de usuario o None si no hay sesión
    """
    return session.get('usuario')


def esta_autenticado() -> bool:
    """
    Verifica si hay una sesión activa
    
    Returns:
        True si hay sesión activa
    """
    return 'usuario' in session
