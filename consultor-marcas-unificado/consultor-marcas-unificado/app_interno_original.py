"""
Consultor de Marcas - Sistema Interno
======================================

Aplicación Flask principal con dashboard, análisis y generación de PDFs.

Autor: Gestor SVG / MarcaSegura
Fecha: Enero 2026
"""

from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, send_file
import logging
from datetime import datetime
import os
import json

# Módulos propios
from config import Config
from auth import (
    login_required, 
    verificar_credenciales, 
    iniciar_sesion, 
    cerrar_sesion,
    obtener_usuario_actual,
    esta_autenticado
)
from google_sheets import GoogleSheetsClient, MockGoogleSheetsClient
from impi_fonetico_COMPLETO import IMPIBuscadorFonetico
from analizador_viabilidad_gemini import AnalizadorViabilidadGemini

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Crear aplicación Flask
app = Flask(__name__)
app.config.from_object(Config)

# Inicializar clientes
# Usar MockClient si no hay URL de Apps Script configurada
if Config.GOOGLE_APPS_SCRIPT_URL and 'YOUR_SCRIPT_ID' not in Config.GOOGLE_APPS_SCRIPT_URL:
    sheets_client = GoogleSheetsClient(Config.GOOGLE_APPS_SCRIPT_URL, Config.TIMEZONE)
    logger.info("✅ Usando GoogleSheetsClient real")
else:
    sheets_client = MockGoogleSheetsClient(Config.GOOGLE_APPS_SCRIPT_URL, Config.TIMEZONE)
    logger.warning("⚠️ Usando MockGoogleSheetsClient para desarrollo")

buscador_impi = IMPIBuscadorFonetico()
analizador_gemini = AnalizadorViabilidadGemini(api_key=Config.GEMINI_API_KEY)

# =============================================================================
# RUTAS DE AUTENTICACIÓN
# =============================================================================

@app.route('/')
def index():
    """Redirige a login o dashboard según si hay sesión"""
    if esta_autenticado():
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    """Página de login"""
    
    # Si ya está autenticado, redirigir a dashboard
    if esta_autenticado():
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        usuario = request.form.get('usuario', '').strip()
        password = request.form.get('password', '').strip()
        
        if verificar_credenciales(usuario, password, Config.USUARIOS_AUTORIZADOS):
            iniciar_sesion(usuario)
            flash(f'¡Bienvenido, {usuario}!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Usuario o contraseña incorrectos', 'error')
    
    return render_template('login.html')


@app.route('/logout')
def logout():
    """Cerrar sesión"""
    cerrar_sesion()
    flash('Sesión cerrada correctamente', 'info')
    return redirect(url_for('login'))


# =============================================================================
# DASHBOARD Y VISTAS PRINCIPALES
# =============================================================================

@app.route('/dashboard')
@login_required
def dashboard():
    """Dashboard principal con lista de leads"""
    
    # Obtener filtro de la URL
    filtro = request.args.get('filtro', 'todos')
    
    # Obtener leads
    leads = sheets_client.obtener_leads(filtro=filtro if filtro != 'todos' else None)
    
    # Obtener estadísticas
    stats = sheets_client.obtener_estadisticas()
    
    return render_template(
        'dashboard.html',
        leads=leads,
        stats=stats,
        filtro_actual=filtro,
        usuario=obtener_usuario_actual()
    )


@app.route('/historial')
@login_required
def historial():
    """Historial de análisis completados"""
    
    # Obtener solo leads analizados
    leads = sheets_client.obtener_leads(filtro='analizados')
    
    return render_template(
        'historial.html',
        leads=leads,
        usuario=obtener_usuario_actual()
    )


# =============================================================================
# ANÁLISIS DE MARCAS
# =============================================================================

@app.route('/analizar/<int:lead_id>')
@login_required
def iniciar_analisis(lead_id):
    """Página de análisis de una marca"""
    
    # Obtener datos del lead por ID
    lead = sheets_client.obtener_lead_por_id(lead_id)
    
    if not lead:
        flash('Lead no encontrado', 'error')
        return redirect(url_for('dashboard'))
    
    # NOTA: Ya no validamos si está pagado - permitimos analizar cualquier lead
    
    return render_template(
        'analizar.html',
        lead=lead,
        usuario=obtener_usuario_actual()
    )


@app.route('/api/buscar-impi', methods=['POST'])
@login_required
def api_buscar_impi():
    """API para ejecutar búsqueda en IMPI"""
    
    try:
        data = request.get_json()
        
        marca = data.get('marca')
        clase = data.get('clase')
        
        if not marca:
            return jsonify({'error': 'Marca requerida'}), 400
        
        logger.info(f"🔍 Búsqueda IMPI iniciada: {marca} (Clase: {clase})")
        
        # Ejecutar búsqueda
        resultado = buscador_impi.buscar_fonetica(
            marca,
            clase_niza=int(clase) if clase else None
        )
        
        if not resultado.exito:
            return jsonify({
                'error': True,
                'mensaje': resultado.error
            }), 500
        
        logger.info(f"✅ Búsqueda IMPI completada: {len(resultado.marcas_encontradas)} marcas")
        
        return jsonify({
            'exito': True,
            'resultado': resultado.to_dict()
        })
    
    except Exception as e:
        logger.error(f"❌ Error en búsqueda IMPI: {str(e)}", exc_info=True)
        return jsonify({
            'error': True,
            'mensaje': str(e)
        }), 500


@app.route('/api/analizar-gemini', methods=['POST'])
@login_required
def api_analizar_gemini():
    """API para analizar con Gemini"""
    
    try:
        data = request.get_json()
        
        # Reconstruir resultado de búsqueda desde JSON
        resultado_busqueda_dict = data.get('resultado_busqueda')
        descripcion = data.get('descripcion')
        
        if not resultado_busqueda_dict:
            return jsonify({'error': 'Resultado de búsqueda requerido'}), 400
        
        logger.info(f"🤖 Análisis Gemini iniciado")
        
        # Convertir dict a objeto ResultadoBusqueda
        from impi_fonetico_COMPLETO import ResultadoBusqueda, MarcaInfo
        
        marcas = [
            MarcaInfo(**marca_dict) 
            for marca_dict in resultado_busqueda_dict.get('marcas_similares', [])
        ]
        
        resultado_busqueda = ResultadoBusqueda(
            marca_consultada=resultado_busqueda_dict['marca_consultada'],
            clase_consultada=resultado_busqueda_dict.get('clase_consultada'),
            fecha_busqueda=datetime.fromisoformat(resultado_busqueda_dict['fecha_busqueda']),
            marcas_encontradas=marcas,
            exito=resultado_busqueda_dict['exito'],
            tiempo_busqueda=resultado_busqueda_dict['tiempo_busqueda'],
            total_registros=resultado_busqueda_dict.get('total_registros', 0),
            error=resultado_busqueda_dict.get('error')
        )
        
        # Analizar con Gemini
        analisis = analizador_gemini.analizar_viabilidad(
            resultado_busqueda,
            descripcion_producto=descripcion
        )
        
        logger.info(f"✅ Análisis Gemini completado: {analisis.porcentaje_viabilidad}%")
        
        return jsonify({
            'exito': True,
            'analisis': analisis.to_dict()
        })
    
    except Exception as e:
        logger.error(f"❌ Error en análisis Gemini: {str(e)}", exc_info=True)
        return jsonify({
            'error': True,
            'mensaje': str(e)
        }), 500


@app.route('/revision/<int:lead_id>')
@login_required
def revision(lead_id):
    """Página de revisión y ajuste del análisis"""
    
    # Obtener datos del lead por ID
    lead = sheets_client.obtener_lead_por_id(lead_id)
    
    if not lead:
        flash('Lead no encontrado', 'error')
        return redirect(url_for('dashboard'))
    
    # Los datos del análisis se pasan como parámetros de sesión
    # o se reconstruyen aquí si es necesario
    
    return render_template(
        'revision.html',
        lead=lead,
        usuario=obtener_usuario_actual()
    )


# =============================================================================
# GENERACIÓN DE PDFs
# =============================================================================

@app.route('/api/generar-pdf', methods=['POST'])
@login_required
def api_generar_pdf():
    """API para generar PDF del reporte"""
    
    try:
        data = request.get_json()
        
        email = data.get('email')
        porcentaje_viabilidad = data.get('porcentaje_viabilidad')
        analisis_dict = data.get('analisis')
        resultado_busqueda_dict = data.get('resultado_busqueda')
        notas_experto = data.get('notas_experto', '')
        
        if not all([email, porcentaje_viabilidad, analisis_dict, resultado_busqueda_dict]):
            return jsonify({'error': 'Datos incompletos'}), 400
        
        logger.info(f"📄 Generando PDF para: {email}")
        
        # Importar generador de PDF
        from generador_pdf import generar_pdf_reporte
        
        # Obtener datos del lead
        lead = sheets_client.obtener_lead_por_email(email)
        
        if not lead:
            return jsonify({'error': 'Lead no encontrado'}), 404
        
        # Generar PDF
        pdf_path = generar_pdf_reporte(
            lead=lead,
            porcentaje_viabilidad=porcentaje_viabilidad,
            analisis=analisis_dict,
            marcas_similares=resultado_busqueda_dict.get('marcas_similares', []),
            total_encontradas=resultado_busqueda_dict.get('total_registros', 0),
            notas_experto=notas_experto
        )
        
        if not pdf_path or not os.path.exists(pdf_path):
            return jsonify({'error': 'Error generando PDF'}), 500
        
        logger.info(f"✅ PDF generado: {pdf_path}")
        
        # Actualizar Sheet
        sheets_client.marcar_analizado(
            email=email,
            porcentaje_viabilidad=int(porcentaje_viabilidad),
            pdf_url=f"/download-pdf/{os.path.basename(pdf_path)}"
        )
        
        if notas_experto:
            sheets_client.agregar_nota_experto(email, notas_experto)
        
        return jsonify({
            'exito': True,
            'pdf_url': f"/download-pdf/{os.path.basename(pdf_path)}",
            'pdf_filename': os.path.basename(pdf_path)
        })
    
    except Exception as e:
        logger.error(f"❌ Error generando PDF: {str(e)}", exc_info=True)
        return jsonify({
            'error': True,
            'mensaje': str(e)
        }), 500


@app.route('/download-pdf/<filename>')
@login_required
def download_pdf(filename):
    """Descarga un PDF generado"""
    
    pdf_path = os.path.join(Config.PDF_FOLDER, filename)
    
    if not os.path.exists(pdf_path):
        flash('PDF no encontrado', 'error')
        return redirect(url_for('dashboard'))
    
    return send_file(
        pdf_path,
        as_attachment=True,
        download_name=filename,
        mimetype='application/pdf'
    )


@app.route('/api/aprobar-pdf', methods=['POST'])
@login_required
def api_aprobar_pdf():
    """API para aprobar un PDF y marcarlo como listo para enviar"""
    
    try:
        data = request.get_json()
        email = data.get('email')
        
        if not email:
            return jsonify({'error': 'Email requerido'}), 400
        
        logger.info(f"✅ Aprobando PDF para: {email}")
        
        # Marcar como aprobado
        sheets_client.marcar_aprobado(email, aprobado=True)
        
        return jsonify({
            'exito': True,
            'mensaje': 'PDF aprobado correctamente'
        })
    
    except Exception as e:
        logger.error(f"❌ Error aprobando PDF: {str(e)}", exc_info=True)
        return jsonify({
            'error': True,
            'mensaje': str(e)
        }), 500


# =============================================================================
# GESTIÓN DE LEADS
# =============================================================================

@app.route('/api/crear-lead', methods=['POST'])
@login_required
def api_crear_lead():
    """API para crear un nuevo lead manualmente"""
    
    try:
        data = request.get_json()
        
        # Validar campos requeridos
        campos_requeridos = ['nombre', 'email', 'telefono', 'marca']
        for campo in campos_requeridos:
            if not data.get(campo):
                return jsonify({
                    'error': True,
                    'mensaje': f'Campo requerido: {campo}'
                }), 400
        
        # Validar formato de email
        email = data.get('email').strip().lower()
        if '@' not in email or '.' not in email:
            return jsonify({
                'error': True,
                'mensaje': 'Email inválido'
            }), 400
        
        # NOTA: Permitimos emails duplicados porque los despachos pueden usar el mismo email para múltiples marcas
        
        # Preparar datos del lead
        nuevo_lead = {
            'fecha': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'nombre': data.get('nombre').strip(),
            'email': email,
            'telefono': data.get('telefono').strip(),
            'marca': data.get('marca').strip(),
            'tipo_negocio': data.get('tipo_negocio', '').strip(),
            'clase_sugerida': data.get('clase_sugerida', ''),
            'status_impi': 'pendiente',
            'pagado': False,
            'analizado': False,
            'pdf_url': '',
            'notas': 'Lead creado manualmente por ' + obtener_usuario_actual()
        }
        
        logger.info(f"📝 Creando nuevo lead manual: {nuevo_lead['nombre']} ({email})")
        
        # Guardar en Google Sheets
        resultado = sheets_client.agregar_lead(nuevo_lead)
        
        if not resultado:
            raise Exception('Error guardando en Google Sheets')
        
        logger.info(f"✅ Lead creado exitosamente: {email}")
        
        return jsonify({
            'exito': True,
            'mensaje': 'Lead creado exitosamente',
            'email': email
        })
    
    except Exception as e:
        logger.error(f"❌ Error creando lead: {str(e)}", exc_info=True)
        return jsonify({
            'error': True,
            'mensaje': str(e)
        }), 500


# =============================================================================
# ENVÍO DE EMAILS (Opcional)
# =============================================================================

@app.route('/api/enviar-email', methods=['POST'])
@login_required
def api_enviar_email():
    """API para enviar email al cliente con el PDF"""
    
    try:
        data = request.get_json()
        
        email = data.get('email')
        pdf_filename = data.get('pdf_filename')
        
        if not all([email, pdf_filename]):
            return jsonify({'error': 'Datos incompletos'}), 400
        
        logger.info(f"📧 Enviando email a: {email}")
        
        # TODO: Implementar envío de email
        # from email_sender import enviar_email_con_pdf
        # resultado = enviar_email_con_pdf(email, pdf_filename)
        
        # Por ahora, simular envío
        sheets_client.marcar_enviado(
            email=email,
            pdf_url=f"/download-pdf/{pdf_filename}"
        )
        
        return jsonify({
            'exito': True,
            'mensaje': 'Email enviado correctamente'
        })
    
    except Exception as e:
        logger.error(f"❌ Error enviando email: {str(e)}", exc_info=True)
        return jsonify({
            'error': True,
            'mensaje': str(e)
        }), 500


# =============================================================================
# UTILIDADES
# =============================================================================

@app.context_processor
def inject_globals():
    """Inyecta variables globales en todos los templates"""
    return {
        'NOMBRE_EMPRESA': Config.NOMBRE_EMPRESA,
        'usuario_actual': obtener_usuario_actual(),
        'esta_autenticado': esta_autenticado()
    }


@app.errorhandler(404)
def not_found(error):
    """Página de error 404"""
    return render_template('404.html'), 404


@app.errorhandler(500)
def internal_error(error):
    """Página de error 500"""
    logger.error(f"Error 500: {str(error)}", exc_info=True)
    return render_template('500.html'), 500


# =============================================================================
# INICIALIZACIÓN
# =============================================================================

if __name__ == '__main__':
    logger.info("="*70)
    logger.info("  CONSULTOR DE MARCAS - SISTEMA INTERNO")
    logger.info("  Puerto: 5000")
    logger.info("  Modo: " + ("Desarrollo" if Config.DEBUG else "Producción"))
    logger.info("="*70)
    
    app.run(
        host='0.0.0.0',
        port=5000,
        debug=Config.DEBUG
    )
