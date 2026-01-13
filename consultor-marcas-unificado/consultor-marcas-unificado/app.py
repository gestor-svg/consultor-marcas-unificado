"""
Consultor de Marcas - Sistema UNIFICADO
========================================

Sistema público (funnel de ventas) + Sistema interno (dashboard de expertos)

Rutas PÚBLICAS (sin login):
- / → Landing o dashboard si autenticado
- /analizar (POST) → Análisis simple denominación
- /capturar-lead (POST) → Guardar lead
- /facturacion → Formulario fiscal
- /confirmacion → Página de gracias
- Páginas legales

Rutas INTERNAS (con @login_required):
- /dashboard → Lista de leads
- /analizar/<id> → Análisis fonético completo
- /revision/<id> → Edición pre-PDF
- APIs de análisis y PDF

Autor: Gestor SVG / MarcaSegura
Fecha: Enero 2026
"""

from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, send_file
import logging
from datetime import datetime
import os
import json
from functools import wraps

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
from impi_denominacion import buscar_impi_denominacion
from analizador_viabilidad_gemini import AnalizadorViabilidadGemini
from utils_public import (
    clasificar_con_gemini,
    enviar_notificacion_push,
    enviar_email_lead,
    generar_whatsapp_lead_nuevo,
    obtener_nombre_clase,
    CLASES_NIZA
)

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
if Config.GOOGLE_APPS_SCRIPT_URL and 'YOUR_SCRIPT_ID' not in Config.GOOGLE_APPS_SCRIPT_URL:
    sheets_client = GoogleSheetsClient(Config.GOOGLE_APPS_SCRIPT_URL, Config.TIMEZONE)
    logger.info("✅ Usando GoogleSheetsClient real")
else:
    sheets_client = MockGoogleSheetsClient(Config.GOOGLE_APPS_SCRIPT_URL, Config.TIMEZONE)
    logger.warning("⚠️ Usando MockGoogleSheetsClient para desarrollo")

buscador_impi = IMPIBuscadorFonetico()
analizador_gemini = AnalizadorViabilidadGemini(api_key=Config.GEMINI_API_KEY)


# =============================================================================
# FUNCIONES AUXILIARES
# =============================================================================

def obtener_fecha_mexico():
    """Obtiene fecha actual en zona horaria de México"""
    return datetime.now(Config.MEXICO_TZ).strftime('%Y-%m-%d')

def obtener_hora_mexico():
    """Obtiene hora actual en zona horaria de México"""
    return datetime.now(Config.MEXICO_TZ).strftime('%H:%M:%S')


# =============================================================================
# RUTAS PÚBLICAS (Sin autenticación requerida)
# =============================================================================

@app.route('/')
def index():
    """Landing público o redirect a dashboard si está autenticado"""
    if esta_autenticado():
        return redirect(url_for('dashboard'))
    return render_template('public/index.html',
                         precio=Config.PRECIO_REPORTE,
                         whatsapp=Config.WHATSAPP_NUMERO)


@app.route('/analizar', methods=['POST'])
def analizar_publico():
    """Análisis público: búsqueda denominación + clasificación Gemini"""
    try:
        data = request.json
        marca = data.get('marca', '').strip()
        descripcion = data.get('descripcion', '').strip()
        tipo_negocio = data.get('tipo', 'servicio').lower()
        
        if not marca or not descripcion:
            return jsonify({"error": "Marca y descripción son obligatorias"}), 400
        
        logger.info(f"\n{'='*70}\nANÁLISIS PÚBLICO: {marca}\n{'='*70}")
        
        # Clasificación con Gemini
        clasificacion = clasificar_con_gemini(descripcion, tipo_negocio, Config.GEMINI_API_KEY)
        
        # Búsqueda simple en IMPI (denominación)
        status_impi = buscar_impi_denominacion(marca)
        
        clase_sugerida = f"Clase {clasificacion['clase_principal']}: {clasificacion['clase_nombre']}"
        
        if status_impi == "POSIBLEMENTE_DISPONIBLE":
            mensaje = f"¡Buenas noticias! No encontramos coincidencias exactas de '{marca}'."
            icono, color = "✓", "success"
            cta = "Se requiere un análisis fonético completo para confirmar disponibilidad."
        elif status_impi == "REQUIERE_ANALISIS":
            mensaje = f"Encontramos registros relacionados con '{marca}' en el IMPI."
            icono, color = "⚠️", "warning"
            cta = "Tu marca o una similar podría estar registrada."
        else:
            mensaje = f"No pudimos conectar con el IMPI."
            icono, color = "🔄", "info"
            cta = "Déjanos tus datos para búsqueda manual."
        
        return jsonify({
            "mensaje": mensaje,
            "icono": icono,
            "color": color,
            "clase_sugerida": clase_sugerida,
            "nota_tecnica": clasificacion.get('nota', ''),
            "mostrar_formulario": True,
            "cta": cta,
            "status_impi": status_impi,
            "tipo_negocio": tipo_negocio,
            "precio_reporte": Config.PRECIO_REPORTE,
        })
        
    except Exception as e:
        logger.error(f"[ERROR analizar_publico] {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/capturar-lead', methods=['POST'])
def capturar_lead():
    """Captura lead inicial desde formulario público"""
    try:
        data = request.json
        
        # Preparar datos del lead
        datos_lead = {
            'nombre': data.get('nombre', ''),
            'email': data.get('email', ''),
            'telefono': data.get('telefono', ''),
            'marca': data.get('marca', ''),
            'tipo_negocio': data.get('tipo_negocio', ''),
            'clase_sugerida': data.get('clase_sugerida', ''),
            'status_impi': data.get('status_impi', ''),
            'pagado': 'FALSE',  # Inicialmente no pagado
            'analizado': 'FALSE',
            'notas': 'Lead capturado desde formulario público'
        }
        
        if not all([datos_lead['nombre'], datos_lead['email'], datos_lead['telefono'], datos_lead['marca']]):
            return jsonify({"success": False, "error": "Todos los campos son obligatorios"}), 400
        
        logger.info(f"\n[LEAD PÚBLICO] {datos_lead['nombre']} - {datos_lead['marca']}")
        
        # Guardar en Google Sheets usando addLead
        resultado = sheets_client.agregar_lead(datos_lead)
        
        if not resultado:
            logger.error("[SHEETS] Error al guardar lead")
            return jsonify({"success": False, "error": "Error al guardar lead"}), 500
        
        logger.info(f"[SHEETS] Lead guardado con ID: {resultado.get('id')}")
        
        # Enviar notificación push
        if Config.NTFY_ENABLED:
            enviar_notificacion_push(datos_lead, Config.NTFY_CHANNEL, Config.APP_BASE_URL)
        
        # Enviar email (opcional)
        if Config.GMAIL_USER and Config.GMAIL_PASSWORD:
            enviar_email_lead(
                datos_lead, 
                Config.GMAIL_USER, 
                Config.GMAIL_PASSWORD, 
                Config.EMAIL_DESTINO,
                Config.MEXICO_TZ
            )
        
        # Responder con oferta
        respuesta = {
            "success": True,
            "mensaje": "¡Gracias! Hemos recibido tu información.",
            "mostrar_oferta": True,
            "oferta": {
                "titulo": "🎯 Obtén el Reporte Completo + Asesoría",
                "precio": Config.PRECIO_REPORTE,
                "precio_formateado": f"${Config.PRECIO_REPORTE:,} MXN",
                "beneficios": [
                    "✓ Análisis fonético y fonográfico completo",
                    "✓ Búsqueda exhaustiva de marcas similares",
                    "✓ Reporte PDF profesional",
                    "✓ Asesoría 1-a-1 por Google Meet (30 min)",
                    "✓ Recomendaciones personalizadas"
                ],
                "link_pago": Config.MERCADO_PAGO_LINK,
            },
        }
        
        return jsonify(respuesta)
        
    except Exception as e:
        logger.error(f"[ERROR capturar_lead] {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/facturacion')
def facturacion():
    """Formulario de facturación post-pago"""
    lead_data = session.get('lead_data', {})
    telefono = lead_data.get('telefono', request.args.get('tel', ''))
    return render_template('public/facturacion.html', telefono=telefono, lead_data=lead_data)


@app.route('/guardar-facturacion', methods=['POST'])
def guardar_facturacion():
    """Guarda datos de facturación"""
    try:
        data = request.json
        
        datos_fact = {
            'telefono': data.get('telefono', ''),
            'email': data.get('email', ''),
            'requiere_factura': data.get('requiere_factura', 'No'),
            'rfc': data.get('rfc', ''),
            'razon_social': data.get('razon_social', ''),
            'regimen_fiscal': data.get('regimen_fiscal', ''),
            'uso_cfdi': data.get('uso_cfdi', ''),
            'codigo_postal': data.get('codigo_postal', ''),
        }
        
        if not datos_fact['telefono'] or not datos_fact['email']:
            return jsonify({"error": "Teléfono y email obligatorios"}), 400
        
        # Guardar en Sheet de facturación (si existe hoja separada)
        # Por ahora solo guardamos en sesión
        session['facturacion_data'] = datos_fact
        
        logger.info(f"[FACTURACIÓN] Datos guardados para {datos_fact['email']}")
        
        return jsonify({"success": True, "redirect": "/confirmacion"})
        
    except Exception as e:
        logger.error(f"[ERROR guardar_facturacion] {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/confirmacion')
def confirmacion():
    """Página de confirmación con calendario y WhatsApp"""
    lead_data = session.get('lead_data', {})
    fact_data = session.get('facturacion_data', {})
    telefono = fact_data.get('telefono', lead_data.get('telefono', ''))
    email_cliente = fact_data.get('email', lead_data.get('email', ''))
    nombre_cliente = lead_data.get('nombre', '')
    
    whatsapp_link = generar_whatsapp_lead_nuevo(lead_data, Config.WHATSAPP_NUMERO, Config.MEXICO_TZ)
    
    return render_template('public/confirmacion.html',
                         telefono=telefono,
                         email_cliente=email_cliente,
                         nombre_cliente=nombre_cliente,
                         cal_com_url=Config.CAL_COM_URL,
                         whatsapp_link=whatsapp_link,
                         mercado_pago_link=Config.MERCADO_PAGO_LINK,
                         lead_data=lead_data)


# Páginas legales
@app.route('/aviso-legal')
def aviso_legal():
    return render_template('public/aviso-legal.html')

@app.route('/terminos-y-condiciones')
def terminos_condiciones():
    return render_template('public/terminos-y-condiciones.html')

@app.route('/politica-de-privacidad')
def politica_privacidad():
    return render_template('public/politica-de-privacidad.html')

@app.route('/aviso-de-cookies')
def aviso_cookies():
    return render_template('public/aviso-de-cookies.html')


# =============================================================================
# RUTAS DE AUTENTICACIÓN
# =============================================================================

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Página de login para expertos"""
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
    
    return render_template('internal/login.html')


@app.route('/logout')
def logout():
    """Cerrar sesión"""
    cerrar_sesion()
    flash('Sesión cerrada correctamente', 'info')
    return redirect(url_for('login'))


# =============================================================================
# DASHBOARD Y VISTAS PRINCIPALES (INTERNAS - Requieren login)
# =============================================================================

@app.route('/dashboard')
@login_required
def dashboard():
    """Dashboard principal con lista de leads"""
    try:
        # Obtener filtros
        filtro_pagado = request.args.get('pagado')
        filtro_analizado = request.args.get('analizado')
        
        # Obtener leads del sheets
        leads = sheets_client.obtener_leads(filtro_pagado=filtro_pagado, filtro_analizado=filtro_analizado)
        
        # Obtener estadísticas
        stats = sheets_client.obtener_estadisticas()
        
        usuario_actual = obtener_usuario_actual()
        
        return render_template(
            'internal/dashboard.html',
            leads=leads,
            stats=stats,
            usuario=usuario_actual,
            filtro_pagado=filtro_pagado,
            filtro_analizado=filtro_analizado
        )
        
    except Exception as e:
        logger.error(f"Error en dashboard: {e}")
        flash(f'Error al cargar dashboard: {str(e)}', 'error')
        return render_template('internal/dashboard.html', leads=[], stats={}, error=str(e))


@app.route('/historial')
@login_required
def historial():
    """Historial de análisis realizados"""
    try:
        # Obtener solo leads analizados
        leads = sheets_client.obtener_leads(filtro_analizado='TRUE')
        
        usuario_actual = obtener_usuario_actual()
        
        return render_template(
            'internal/historial.html',
            leads=leads,
            usuario=usuario_actual
        )
        
    except Exception as e:
        logger.error(f"Error en historial: {e}")
        flash(f'Error al cargar historial: {str(e)}', 'error')
        return render_template('internal/historial.html', leads=[], error=str(e))


@app.route('/analizar/<int:lead_id>')
@login_required
def iniciar_analisis(lead_id):
    """Página de análisis fonético COMPLETO (versión interna)"""
    try:
        # Obtener lead por ID
        lead = sheets_client.obtener_lead_por_id(lead_id)
        
        if not lead:
            flash(f'Lead #{lead_id} no encontrado', 'error')
            return redirect(url_for('dashboard'))
        
        usuario_actual = obtener_usuario_actual()
        
        return render_template(
            'internal/analizar.html',
            lead=lead,
            usuario=usuario_actual,
            lead_id=lead_id
        )
        
    except Exception as e:
        logger.error(f"Error en iniciar_analisis: {e}")
        flash(f'Error al cargar análisis: {str(e)}', 'error')
        return redirect(url_for('dashboard'))


# =============================================================================
# APIs INTERNAS (Requieren login)
# =============================================================================

@app.route('/api/buscar-impi', methods=['POST'])
@login_required
def api_buscar_impi():
    """API: Búsqueda fonética COMPLETA en IMPI"""
    try:
        data = request.json
        marca = data.get('marca', '').strip()
        clase = data.get('clase', '')
        
        if not marca:
            return jsonify({"success": False, "error": "Marca requerida"}), 400
        
        logger.info(f"\n[BÚSQUEDA FONÉTICA] Marca: {marca}, Clase: {clase}")
        
        # Ejecutar búsqueda fonética (puede tardar ~30 seg)
        resultado = buscador_impi.buscar_marca(marca, clase_niza=clase if clase else None)
        
        if not resultado["exito"]:
            return jsonify({
                "success": False,
                "error": resultado.get("error", "Error en búsqueda")
            }), 500
        
        marcas = resultado.get("marcas", [])
        
        logger.info(f"[BÚSQUEDA FONÉTICA] ✓ {len(marcas)} marcas encontradas")
        
        return jsonify({
            "success": True,
            "total_marcas": len(marcas),
            "marcas": [marca.to_dict() for marca in marcas],
            "mensaje": resultado.get("mensaje", "")
        })
        
    except Exception as e:
        logger.error(f"Error en api_buscar_impi: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/analizar-gemini', methods=['POST'])
@login_required
def api_analizar_gemini():
    """API: Análisis de viabilidad con Gemini"""
    try:
        data = request.json
        marca_consulta = data.get('marca_consulta', '').strip()
        clase_consulta = data.get('clase_consulta', '')
        marcas_encontradas = data.get('marcas_encontradas', [])
        
        if not marca_consulta or not marcas_encontradas:
            return jsonify({"success": False, "error": "Datos incompletos"}), 400
        
        logger.info(f"\n[ANÁLISIS GEMINI] Marca: {marca_consulta}, Total marcas: {len(marcas_encontradas)}")
        
        # Analizar con Gemini
        analisis = analizador_gemini.analizar_viabilidad(
            marca_consulta=marca_consulta,
            clase_consulta=clase_consulta,
            marcas_encontradas=marcas_encontradas
        )
        
        if not analisis["exito"]:
            return jsonify({
                "success": False,
                "error": analisis.get("error", "Error en análisis")
            }), 500
        
        logger.info(f"[ANÁLISIS GEMINI] ✓ Viabilidad: {analisis.get('porcentaje_viabilidad')}%")
        
        return jsonify({
            "success": True,
            **analisis
        })
        
    except Exception as e:
        logger.error(f"Error en api_analizar_gemini: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/revision/<int:lead_id>')
@login_required
def revision(lead_id):
    """Página de revisión y edición pre-PDF"""
    try:
        lead = sheets_client.obtener_lead_por_id(lead_id)
        
        if not lead:
            flash(f'Lead #{lead_id} no encontrado', 'error')
            return redirect(url_for('dashboard'))
        
        # Obtener análisis de la sesión o DB
        analisis = session.get(f'analisis_{lead_id}')
        
        if not analisis:
            flash('No hay análisis disponible. Realiza el análisis primero.', 'warning')
            return redirect(url_for('iniciar_analisis', lead_id=lead_id))
        
        usuario_actual = obtener_usuario_actual()
        
        return render_template(
            'internal/revision.html',
            lead=lead,
            analisis=analisis,
            usuario=usuario_actual,
            lead_id=lead_id
        )
        
    except Exception as e:
        logger.error(f"Error en revision: {e}")
        flash(f'Error al cargar revisión: {str(e)}', 'error')
        return redirect(url_for('dashboard'))


@app.route('/api/generar-pdf', methods=['POST'])
@login_required
def api_generar_pdf():
    """API: Generar PDF con análisis editado"""
    try:
        from generador_pdf import GeneradorPDF
        
        data = request.json
        lead_id = data.get('lead_id')
        
        if not lead_id:
            return jsonify({"success": False, "error": "lead_id requerido"}), 400
        
        lead = sheets_client.obtener_lead_por_id(lead_id)
        
        if not lead:
            return jsonify({"success": False, "error": "Lead no encontrado"}), 404
        
        # Datos editados del análisis
        datos_analisis = {
            'marca_consulta': data.get('marca_consulta', lead.get('marca', '')),
            'clase_consulta': data.get('clase_consulta', lead.get('clase_sugerida', '')),
            'porcentaje_viabilidad': data.get('porcentaje_viabilidad', 0),
            'analisis_principal': data.get('analisis_principal', ''),
            'factores_riesgo': data.get('factores_riesgo', []),
            'factores_favorables': data.get('factores_favorables', []),
            'recomendaciones': data.get('recomendaciones', []),
            'notas_experto': data.get('notas_experto', ''),
            'marcas_conflictivas': data.get('marcas_conflictivas', []),
        }
        
        # Generar PDF
        generador = GeneradorPDF(Config.PDF_FOLDER, Config.PDF_LOGO_PATH)
        pdf_path = generador.generar_reporte(lead, datos_analisis)
        
        if not pdf_path or not os.path.exists(pdf_path):
            return jsonify({"success": False, "error": "Error al generar PDF"}), 500
        
        # Obtener nombre del archivo
        pdf_filename = os.path.basename(pdf_path)
        
        # Guardar URL del PDF en el lead
        pdf_url = url_for('download_pdf', filename=pdf_filename, _external=True)
        
        # Guardar en sesión para aprobar después
        session[f'pdf_generado_{lead_id}'] = {
            'filename': pdf_filename,
            'url': pdf_url,
            'analisis': datos_analisis
        }
        
        logger.info(f"[PDF] ✓ Generado: {pdf_filename}")
        
        return jsonify({
            "success": True,
            "pdf_url": pdf_url,
            "pdf_filename": pdf_filename,
            "mensaje": "PDF generado correctamente"
        })
        
    except Exception as e:
        logger.error(f"Error en api_generar_pdf: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/download-pdf/<filename>')
@login_required
def download_pdf(filename):
    """Descargar PDF generado"""
    try:
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
        
    except Exception as e:
        logger.error(f"Error en download_pdf: {e}")
        flash(f'Error al descargar PDF: {str(e)}', 'error')
        return redirect(url_for('dashboard'))


@app.route('/api/aprobar-pdf', methods=['POST'])
@login_required
def api_aprobar_pdf():
    """API: Aprobar PDF y marcar lead como analizado"""
    try:
        data = request.json
        lead_id = data.get('lead_id')
        
        if not lead_id:
            return jsonify({"success": False, "error": "lead_id requerido"}), 400
        
        # Obtener datos del PDF de la sesión
        pdf_data = session.get(f'pdf_generado_{lead_id}')
        
        if not pdf_data:
            return jsonify({"success": False, "error": "No hay PDF generado"}), 400
        
        # Actualizar lead en Sheet
        datos_actualizacion = {
            'analizado': 'TRUE',
            'pdf_url': pdf_data['url'],
            'notas': f"Análisis completado por {obtener_usuario_actual()}"
        }
        
        resultado = sheets_client.actualizar_lead(lead_id, datos_actualizacion)
        
        if not resultado:
            return jsonify({"success": False, "error": "Error al actualizar lead"}), 500
        
        logger.info(f"[APROBAR PDF] ✓ Lead #{lead_id} marcado como analizado")
        
        return jsonify({
            "success": True,
            "mensaje": "Lead marcado como analizado",
            "redirect_url": url_for('dashboard')
        })
        
    except Exception as e:
        logger.error(f"Error en api_aprobar_pdf: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/crear-lead', methods=['POST'])
@login_required
def api_crear_lead():
    """API: Crear lead manualmente desde dashboard"""
    try:
        data = request.json
        
        datos_lead = {
            'nombre': data.get('nombre', '').strip(),
            'email': data.get('email', '').strip(),
            'telefono': data.get('telefono', '').strip(),
            'marca': data.get('marca', '').strip(),
            'tipo_negocio': data.get('tipo_negocio', '').strip(),
            'clase_sugerida': data.get('clase_sugerida', '').strip(),
            'pagado': 'FALSE',
            'analizado': 'FALSE',
            'notas': f"Lead creado manualmente por {obtener_usuario_actual()}"
        }
        
        # Validar campos requeridos
        if not all([datos_lead['nombre'], datos_lead['email'], datos_lead['telefono'], datos_lead['marca']]):
            return jsonify({"success": False, "error": "Nombre, email, teléfono y marca son obligatorios"}), 400
        
        # Guardar en Sheet
        resultado = sheets_client.agregar_lead(datos_lead)
        
        if not resultado:
            return jsonify({"success": False, "error": "Error al guardar lead"}), 500
        
        logger.info(f"[CREAR LEAD] ✓ Lead creado manualmente: {datos_lead['nombre']} - {datos_lead['marca']}")
        
        return jsonify({
            "success": True,
            "mensaje": "Lead creado correctamente",
            "lead_id": resultado.get('id')
        })
        
    except Exception as e:
        logger.error(f"Error en api_crear_lead: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/enviar-email', methods=['POST'])
@login_required
def api_enviar_email():
    """API: Enviar email al cliente con PDF"""
    try:
        # TODO: Implementar envío de email
        return jsonify({
            "success": True,
            "mensaje": "Función de email pendiente de implementar"
        })
        
    except Exception as e:
        logger.error(f"Error en api_enviar_email: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


# =============================================================================
# CONTEXT PROCESSORS Y ERROR HANDLERS
# =============================================================================

@app.context_processor
def inject_globals():
    """Inyecta variables globales a todos los templates"""
    return {
        'usuario_actual': obtener_usuario_actual() if esta_autenticado() else None,
        'esta_autenticado': esta_autenticado(),
        'nombre_empresa': Config.NOMBRE_EMPRESA,
        'whatsapp_numero': Config.WHATSAPP_NUMERO,
        'email_contacto': Config.EMAIL_CONTACTO,
    }


@app.errorhandler(404)
def not_found(error):
    """Manejador de error 404"""
    if esta_autenticado():
        return render_template('internal/404.html'), 404
    return render_template('public/index.html'), 404


@app.errorhandler(500)
def internal_error(error):
    """Manejador de error 500"""
    logger.error(f"Error 500: {error}")
    if esta_autenticado():
        return render_template('internal/500.html'), 500
    return "Error interno del servidor", 500


# =============================================================================
# RUTA DE HEALTH CHECK
# =============================================================================

@app.route('/health')
def health():
    """Health check para monitoreo"""
    return jsonify({
        "status": "ok",
        "version": "unificado-1.0",
        "precio": Config.PRECIO_REPORTE,
        "sistema": "público + interno"
    })


# =============================================================================
# MAIN
# =============================================================================

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    print(f"\n{'='*70}")
    print(f"🌐 CONSULTOR DE MARCAS - SISTEMA UNIFICADO")
    print(f"🔓 Público: Landing, formulario, funnel")
    print(f"🔐 Interno: Dashboard, análisis, PDFs")
    print(f"URL: {Config.APP_BASE_URL}")
    print(f"Precio: ${Config.PRECIO_REPORTE} MXN")
    print(f"{'='*70}\n")
    app.run(host='0.0.0.0', port=port, debug=Config.DEBUG)
