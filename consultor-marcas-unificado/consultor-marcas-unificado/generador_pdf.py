"""
Generador de PDF Profesional
============================

Genera reportes de viabilidad de marca en formato PDF profesional.
"""

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, Image, KeepTogether
)
from reportlab.pdfgen import canvas
from datetime import datetime
import os
import logging

logger = logging.getLogger(__name__)


def _crear_encabezado_pie(canvas_obj, doc):
    """Crea encabezado y pie de página"""
    canvas_obj.saveState()
    
    # Pie de página
    canvas_obj.setFont('Helvetica', 8)
    canvas_obj.setFillColor(colors.grey)
    canvas_obj.drawCentredString(
        letter[0] / 2,
        0.5 * inch,
        "MarcaSegura.com.mx | gestor@marcasegura.com.mx | WhatsApp: 523331562224"
    )
    
    # Número de página
    canvas_obj.drawRightString(
        letter[0] - 0.75 * inch,
        0.5 * inch,
        f"Página {doc.page}"
    )
    
    canvas_obj.restoreState()


def clasificar_viabilidad(porcentaje):
    """Clasifica el porcentaje de viabilidad"""
    if porcentaje <= 25:
        return ("MUY BAJA", colors.HexColor('#c0392b'), "No recomendado registrar")
    elif porcentaje <= 50:
        return ("BAJA", colors.HexColor('#e67e22'), "Riesgoso, considerar alternativas")
    elif porcentaje <= 65:
        return ("MEDIA", colors.HexColor('#f39c12'), "Posible con modificaciones")
    else:
        return ("ALTA", colors.HexColor('#27ae60'), "Recomendado para registro")


def generar_pdf_reporte(
    lead: dict,
    porcentaje_viabilidad: int,
    analisis: dict,
    marcas_similares: list,
    total_encontradas: int,
    notas_experto: str = "",
    output_folder: str = None
) -> str:
    """
    Genera PDF profesional con el reporte de viabilidad
    
    Args:
        lead: Datos del lead desde Google Sheets
        porcentaje_viabilidad: Porcentaje de viabilidad (0-85)
        analisis: Diccionario con análisis de Gemini
        marcas_similares: Lista de marcas similares encontradas
        total_encontradas: Total de marcas encontradas
        notas_experto: Notas adicionales del experto
        output_folder: Carpeta donde guardar el PDF
    
    Returns:
        Path del PDF generado
    """
    
    try:
        # Configurar carpeta de salida
        if not output_folder:
            from config import Config
            output_folder = Config.PDF_FOLDER
        
        os.makedirs(output_folder, exist_ok=True)
        
        # Nombre del archivo
        marca_slug = lead['marca'].replace(' ', '_').lower()
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"reporte_{marca_slug}_{timestamp}.pdf"
        filepath = os.path.join(output_folder, filename)
        
        logger.info(f"📄 Generando PDF: {filename}")
        
        # Crear documento
        doc = SimpleDocTemplate(
            filepath,
            pagesize=letter,
            rightMargin=0.75*inch,
            leftMargin=0.75*inch,
            topMargin=1*inch,
            bottomMargin=1*inch
        )
        
        # Contenedor para elementos
        story = []
        
        # Estilos
        styles = getSampleStyleSheet()
        
        # Estilos personalizados
        titulo_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#2c3e50'),
            spaceAfter=10,
            alignment=TA_CENTER,
            fontName='Helvetica-Bold'
        )
        
        subtitulo_style = ParagraphStyle(
            'CustomSubtitle',
            parent=styles['Normal'],
            fontSize=12,
            textColor=colors.HexColor('#7f8c8d'),
            spaceAfter=30,
            alignment=TA_CENTER
        )
        
        heading2_style = ParagraphStyle(
            'CustomHeading2',
            parent=styles['Heading2'],
            fontSize=16,
            textColor=colors.HexColor('#2c3e50'),
            spaceAfter=15,
            spaceBefore=20,
            fontName='Helvetica-Bold'
        )
        
        normal_style = ParagraphStyle(
            'CustomNormal',
            parent=styles['Normal'],
            fontSize=10,
            alignment=TA_JUSTIFY,
            spaceAfter=10
        )
        
        # =====================================================================
        # PORTADA
        # =====================================================================
        
        story.append(Spacer(1, 1.5*inch))
        
        # Logo (si existe)
        from config import Config
        if os.path.exists(Config.PDF_LOGO_PATH):
            try:
                logo = Image(Config.PDF_LOGO_PATH, width=2*inch, height=1*inch)
                logo.hAlign = 'CENTER'
                story.append(logo)
                story.append(Spacer(1, 0.3*inch))
            except:
                logger.warning("⚠️ No se pudo cargar el logo")
        
        story.append(Paragraph("EXAMEN DE VIABILIDAD DE MARCA", titulo_style))
        story.append(Paragraph("Análisis Profesional de Registro", subtitulo_style))
        
        # Información del cliente
        info_cliente = [
            ["Cliente:", lead['nombre']],
            ["Email:", lead['email']],
            ["Marca solicitada:", f"<b>{lead['marca']}</b>"],
            ["Clase Niza:", lead.get('clase_sugerida', 'No especificada')],
            ["Descripción:", lead.get('descripcion', 'N/A')],
            ["Fecha:", datetime.now().strftime('%d/%m/%Y')]
        ]
        
        tabla_info = Table(info_cliente, colWidths=[2*inch, 4*inch])
        tabla_info.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#ecf0f1')),
            ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#2c3e50')),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('ROWBACKGROUNDS', (0, 0), (-1, -1), [colors.white, colors.HexColor('#f8f9fa')])
        ]))
        
        story.append(tabla_info)
        story.append(PageBreak())
        
        # =====================================================================
        # RESULTADO DE VIABILIDAD
        # =====================================================================
        
        story.append(Paragraph("RESULTADO DE VIABILIDAD", heading2_style))
        story.append(Spacer(1, 0.2*inch))
        
        # Clasificación
        categoria, color_viab, descripcion = clasificar_viabilidad(porcentaje_viabilidad)
        
        # Porcentaje con color
        viab_style = ParagraphStyle(
            'Viabilidad',
            parent=styles['Normal'],
            fontSize=60,
            textColor=color_viab,
            alignment=TA_CENTER,
            fontName='Helvetica-Bold',
            spaceAfter=10
        )
        
        story.append(Paragraph(f"{porcentaje_viabilidad}%", viab_style))
        
        cat_style = ParagraphStyle(
            'Categoria',
            parent=styles['Normal'],
            fontSize=14,
            textColor=color_viab,
            alignment=TA_CENTER,
            fontName='Helvetica-Bold',
            spaceAfter=5
        )
        
        story.append(Paragraph(f"VIABILIDAD {categoria}", cat_style))
        story.append(Paragraph(descripcion, subtitulo_style))
        
        # Nivel de riesgo
        nivel_riesgo = analisis.get('nivel_riesgo', 'MEDIO')
        story.append(Paragraph(f"<b>Nivel de riesgo:</b> {nivel_riesgo}", normal_style))
        story.append(Spacer(1, 0.3*inch))
        
        # =====================================================================
        # MARCAS SIMILARES ENCONTRADAS
        # =====================================================================
        
        story.append(Paragraph("MARCAS SIMILARES ENCONTRADAS", heading2_style))
        story.append(Paragraph(
            f"Total de registros detectados en el IMPI: <b>{total_encontradas}</b>",
            normal_style
        ))
        story.append(Spacer(1, 0.1*inch))
        
        if marcas_similares:
            # Mostrar hasta 15 marcas
            marcas_mostrar = marcas_similares[:15]
            
            # Tabla de marcas
            data_marcas = [['#', 'Denominación', 'Expediente', 'Clase', 'Titular']]
            
            for i, marca in enumerate(marcas_mostrar, 1):
                denominacion = marca.get('denominacion', 'N/A')[:30]
                expediente = marca.get('expediente', 'N/A')
                clase = marca.get('clase', 'N/A')
                titular = marca.get('titular', 'N/A')[:35]
                
                data_marcas.append([
                    str(i),
                    denominacion,
                    expediente,
                    clase,
                    titular
                ])
            
            tabla_marcas = Table(
                data_marcas,
                colWidths=[0.3*inch, 1.8*inch, 1*inch, 0.5*inch, 2.4*inch]
            )
            
            tabla_marcas.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#34495e')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 9),
                ('FONTSIZE', (0, 1), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
                ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#ecf0f1')),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8f9fa')])
            ]))
            
            story.append(tabla_marcas)
            
            if len(marcas_similares) > 15:
                story.append(Spacer(1, 0.1*inch))
                story.append(Paragraph(
                    f"<i>... y {len(marcas_similares) - 15} marcas más no mostradas en esta tabla.</i>",
                    normal_style
                ))
        else:
            story.append(Paragraph(
                "No se encontraron marcas fonéticamente similares en la base de datos del IMPI.",
                normal_style
            ))
        
        story.append(Spacer(1, 0.3*inch))
        
        # =====================================================================
        # MARCAS POTENCIALMENTE CONFLICTIVAS
        # =====================================================================
        
        marcas_conflictivas = analisis.get('marcas_conflictivas', [])
        
        if marcas_conflictivas:
            story.append(Paragraph("MARCAS POTENCIALMENTE CONFLICTIVAS", heading2_style))
            story.append(Paragraph(
                "Las siguientes marcas representan el mayor riesgo de conflicto:",
                normal_style
            ))
            story.append(Spacer(1, 0.1*inch))
            
            for i, marca_conf in enumerate(marcas_conflictivas[:5], 1):
                denom = marca_conf.get('denominacion', 'N/A')
                exp = marca_conf.get('expediente', 'N/A')
                razon = marca_conf.get('razon_conflicto', 'N/A')
                nivel = marca_conf.get('nivel_conflicto', 'N/A')
                
                texto = f"""
                <b>{i}. {denom}</b> (Exp: {exp})<br/>
                <i>Razón del conflicto:</i> {razon}<br/>
                <i>Nivel de conflicto:</i> {nivel}
                """
                
                story.append(Paragraph(texto, normal_style))
                story.append(Spacer(1, 0.1*inch))
        
        story.append(PageBreak())
        
        # =====================================================================
        # ANÁLISIS Y RECOMENDACIONES
        # =====================================================================
        
        story.append(Paragraph("ANÁLISIS Y RECOMENDACIONES", heading2_style))
        
        # Análisis detallado
        analisis_texto = analisis.get('analisis_detallado', 'No disponible')
        story.append(Paragraph("<b>Análisis de IA:</b>", normal_style))
        story.append(Paragraph(analisis_texto, normal_style))
        story.append(Spacer(1, 0.2*inch))
        
        # Factores de riesgo
        factores_riesgo = analisis.get('factores_riesgo', [])
        if factores_riesgo:
            story.append(Paragraph("<b>⚠️ Factores de Riesgo:</b>", normal_style))
            for factor in factores_riesgo:
                story.append(Paragraph(f"• {factor}", normal_style))
            story.append(Spacer(1, 0.1*inch))
        
        # Factores favorables
        factores_favorables = analisis.get('factores_favorables', [])
        if factores_favorables:
            story.append(Paragraph("<b>✓ Factores Favorables:</b>", normal_style))
            for factor in factores_favorables:
                story.append(Paragraph(f"• {factor}", normal_style))
            story.append(Spacer(1, 0.1*inch))
        
        # Recomendaciones
        recomendaciones = analisis.get('recomendaciones', [])
        if recomendaciones:
            story.append(Spacer(1, 0.2*inch))
            story.append(Paragraph("<b>💡 Recomendaciones:</b>", normal_style))
            for i, rec in enumerate(recomendaciones, 1):
                story.append(Paragraph(f"{i}. {rec}", normal_style))
        
        # Notas del experto
        if notas_experto and notas_experto.strip():
            story.append(Spacer(1, 0.3*inch))
            story.append(Paragraph("<b>📝 Notas del Experto:</b>", normal_style))
            story.append(Paragraph(notas_experto, normal_style))
        
        story.append(Spacer(1, 0.5*inch))
        
        # =====================================================================
        # DISCLAIMER
        # =====================================================================
        
        disclaimer_style = ParagraphStyle(
            'Disclaimer',
            parent=styles['Normal'],
            fontSize=9,
            textColor=colors.HexColor('#7f8c8d'),
            alignment=TA_JUSTIFY,
            spaceAfter=5
        )
        
        story.append(Paragraph("<b>DISCLAIMER LEGAL:</b>", disclaimer_style))
        
        disclaimer_texto = """
        Este análisis es orientativo y se basa en la información disponible en la base de datos
        pública del Instituto Mexicano de la Propiedad Industrial (IMPI) al momento de la consulta.
        No constituye una garantía de registro ni reemplaza el examen oficial que realizará el IMPI.
        La decisión final sobre el registro de la marca corresponde exclusivamente al examinador
        del IMPI. Se recomienda consultar con un abogado especializado en propiedad intelectual
        antes de proceder con el registro formal.
        """
        
        story.append(Paragraph(disclaimer_texto, disclaimer_style))
        story.append(Spacer(1, 0.3*inch))
        
        # Información de contacto
        contacto_style = ParagraphStyle(
            'Contacto',
            parent=styles['Normal'],
            fontSize=10,
            textColor=colors.HexColor('#2c3e50'),
            alignment=TA_CENTER
        )
        
        story.append(Paragraph("<b>MarcaSegura.com.mx</b>", contacto_style))
        story.append(Paragraph("gestor@marcasegura.com.mx | WhatsApp: 523331562224", contacto_style))
        
        # =====================================================================
        # CONSTRUIR PDF
        # =====================================================================
        
        doc.build(story, onFirstPage=_crear_encabezado_pie, onLaterPages=_crear_encabezado_pie)
        
        logger.info(f"✅ PDF generado exitosamente: {filepath}")
        
        return filepath
    
    except Exception as e:
        logger.error(f"❌ Error generando PDF: {str(e)}", exc_info=True)
        return None
