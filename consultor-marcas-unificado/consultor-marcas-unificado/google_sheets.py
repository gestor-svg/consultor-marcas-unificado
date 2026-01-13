"""
Integración con Google Sheets
==============================

Lectura y escritura de leads en Google Sheets usando Apps Script.
"""

import requests
import logging
from typing import List, Dict, Optional
from datetime import datetime
import pytz

logger = logging.getLogger(__name__)


class GoogleSheetsClient:
    """Cliente para interactuar con Google Sheets via Apps Script"""
    
    def __init__(self, apps_script_url: str, timezone: str = 'America/Mexico_City'):
        """
        Inicializa el cliente
        
        Args:
            apps_script_url: URL del Apps Script desplegado
            timezone: Zona horaria para las fechas
        """
        self.apps_script_url = apps_script_url
        self.timezone = pytz.timezone(timezone)
    
    def obtener_leads(
        self,
        filtro: Optional[str] = None,
        limite: Optional[int] = None
    ) -> List[Dict]:
        """
        Obtiene los leads del Google Sheet
        
        Args:
            filtro: 'pagados', 'no_pagados', 'analizados', 'pendientes', None para todos
            limite: Número máximo de leads a retornar
        
        Returns:
            Lista de diccionarios con los datos de los leads
        """
        
        try:
            params = {
                'action': 'getLeads',
                'filtro': filtro or 'todos'
            }
            
            if limite:
                params['limite'] = limite
            
            logger.info(f"Obteniendo leads con filtro: {filtro}")
            
            response = requests.get(
                self.apps_script_url,
                params=params,
                timeout=30
            )
            
            response.raise_for_status()
            data = response.json()
            
            if not data.get('success'):
                logger.error(f"Error obteniendo leads: {data.get('error')}")
                return []
            
            leads = data.get('leads', [])
            logger.info(f"✅ Obtenidos {len(leads)} leads")
            
            return leads
        
        except Exception as e:
            logger.error(f"Error obteniendo leads: {str(e)}")
            return []
    
    def obtener_lead_por_email(self, email: str) -> Optional[Dict]:
        """
        Obtiene un lead específico por email
        
        Args:
            email: Email del lead
        
        Returns:
            Diccionario con datos del lead o None si no existe
        """
        
        try:
            params = {
                'action': 'getLead',
                'email': email
            }
            
            response = requests.get(
                self.apps_script_url,
                params=params,
                timeout=30
            )
            
            response.raise_for_status()
            data = response.json()
            
            if not data.get('success'):
                return None
            
            return data.get('lead')
        
        except Exception as e:
            logger.error(f"Error obteniendo lead: {str(e)}")
            return None
    
    def obtener_lead_por_id(self, lead_id: int) -> Optional[Dict]:
        """
        Obtiene un lead específico por su ID
        
        Args:
            lead_id: ID del lead
        
        Returns:
            Diccionario con los datos del lead o None si no se encuentra
        """
        
        try:
            params = {
                'action': 'getLeadById',
                'id': str(lead_id)
            }
            
            response = requests.get(
                self.apps_script_url,
                params=params,
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    return data.get('lead')
            
            return None
        
        except Exception as e:
            logger.error(f"Error obteniendo lead por ID: {str(e)}")
            return None
    
    def actualizar_lead(
        self,
        email: str,
        campos: Dict
    ) -> bool:
        """
        Actualiza un lead en el Google Sheet
        
        Args:
            email: Email del lead (identificador único)
            campos: Diccionario con campos a actualizar
        
        Returns:
            True si se actualizó correctamente
        """
        
        try:
            data = {
                'action': 'updateLead',
                'email': email,
                **campos
            }
            
            logger.info(f"Actualizando lead {email}: {list(campos.keys())}")
            
            response = requests.post(
                self.apps_script_url,
                json=data,
                timeout=30
            )
            
            response.raise_for_status()
            result = response.json()
            
            if result.get('success'):
                logger.info(f"✅ Lead actualizado: {email}")
                return True
            else:
                logger.error(f"Error actualizando lead: {result.get('error')}")
                return False
        
        except Exception as e:
            logger.error(f"Error actualizando lead: {str(e)}")
            return False
    
    def marcar_analizado(
        self,
        email: str,
        porcentaje_viabilidad: int,
        pdf_url: Optional[str] = None
    ) -> bool:
        """
        Marca un lead como analizado
        
        Args:
            email: Email del lead
            porcentaje_viabilidad: Porcentaje de viabilidad calculado
            pdf_url: URL del PDF generado (opcional)
        
        Returns:
            True si se actualizó correctamente
        """
        
        ahora = datetime.now(self.timezone).strftime('%Y-%m-%d %H:%M:%S')
        
        campos = {
            'analizado': 'TRUE',
            'fecha_analisis': ahora,
            'porcentaje_viabilidad': porcentaje_viabilidad
        }
        
        if pdf_url:
            campos['pdf_url'] = pdf_url
        
        return self.actualizar_lead(email, campos)
    
    def marcar_aprobado(
        self,
        email: str,
        aprobado: bool = True
    ) -> bool:
        """
        Marca un lead como aprobado por el experto
        
        Args:
            email: Email del lead
            aprobado: True para aprobar, False para desaprobar
        
        Returns:
            True si se actualizó correctamente
        """
        
        ahora = datetime.now(self.timezone).strftime('%Y-%m-%d %H:%M:%S')
        
        campos = {
            'aprobado': 'TRUE' if aprobado else 'FALSE',
            'fecha_aprobacion': ahora if aprobado else ''
        }
        
        return self.actualizar_lead(email, campos)
    
    def marcar_enviado(
        self,
        email: str,
        pdf_url: str
    ) -> bool:
        """
        Marca un lead como enviado al cliente
        
        Args:
            email: Email del lead
            pdf_url: URL del PDF enviado
        
        Returns:
            True si se actualizó correctamente
        """
        
        ahora = datetime.now(self.timezone).strftime('%Y-%m-%d %H:%M:%S')
        
        campos = {
            'enviado_cliente': 'TRUE',
            'fecha_envio': ahora,
            'pdf_url': pdf_url
        }
        
        return self.actualizar_lead(email, campos)
    
    def agregar_nota_experto(
        self,
        email: str,
        nota: str
    ) -> bool:
        """
        Agrega o actualiza nota del experto
        
        Args:
            email: Email del lead
            nota: Texto de la nota
        
        Returns:
            True si se actualizó correctamente
        """
        
        return self.actualizar_lead(email, {'notas_experto': nota})
    
    def agregar_lead(self, lead_data: Dict) -> bool:
        """
        Agrega un nuevo lead a Google Sheets
        
        Args:
            lead_data: Diccionario con los datos del lead
                      Campos esperados: fecha, nombre, email, telefono, marca,
                      tipo_negocio, clase_sugerida, status_impi, pagado, analizado, pdf_url, notas
        
        Returns:
            True si se agregó correctamente
        """
        
        try:
            params = {
                'action': 'addLead'
            }
            
            # Convertir booleanos a strings para Google Sheets
            lead_formatted = lead_data.copy()
            if 'pagado' in lead_formatted:
                lead_formatted['pagado'] = 'TRUE' if lead_formatted['pagado'] else 'FALSE'
            if 'analizado' in lead_formatted:
                lead_formatted['analizado'] = 'TRUE' if lead_formatted['analizado'] else 'FALSE'
            
            response = requests.post(
                self.apps_script_url,
                json={
                    **params,
                    'leadData': lead_formatted
                },
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get('success'):
                    logger.info(f"✅ Lead agregado exitosamente: {lead_data.get('email')}")
                    return True
                else:
                    logger.error(f"Error agregando lead: {result.get('error', 'Unknown error')}")
                    return False
            else:
                logger.error(f"Error HTTP agregando lead: {response.status_code}")
                return False
        
        except Exception as e:
            logger.error(f"Error agregando lead: {str(e)}")
            return False
    
    def obtener_estadisticas(self) -> Dict:
        """
        Obtiene estadísticas generales de los leads
        
        Returns:
            Diccionario con estadísticas
        """
        
        try:
            params = {
                'action': 'getStats'
            }
            
            response = requests.get(
                self.apps_script_url,
                params=params,
                timeout=30
            )
            
            response.raise_for_status()
            data = response.json()
            
            if data.get('success'):
                return data.get('stats', {})
            
            return {}
        
        except Exception as e:
            logger.error(f"Error obteniendo estadísticas: {str(e)}")
            return {}


# =============================================================================
# MOCK CLIENT PARA DESARROLLO (cuando no hay internet o Apps Script)
# =============================================================================

class MockGoogleSheetsClient:
    """Cliente mock para desarrollo sin conexión real a Sheets"""
    
    def __init__(self, apps_script_url: str, timezone: str = 'America/Mexico_City'):
        self.apps_script_url = apps_script_url
        self.timezone = pytz.timezone(timezone)
        
        # Datos de prueba
        self.leads_mock = [
            {
                'fecha': '2026-01-06',
                'hora': '10:30:00',
                'nombre': 'Juan Pérez',
                'email': 'juan@example.com',
                'telefono': '523331234567',
                'marca': 'MI MARCA',
                'descripcion': 'Venta de ropa deportiva',
                'tipo_negocio': 'Comercio',
                'clase_sugerida': '25',
                'status_impi': 'DISPONIBLE',
                'pagado': 'TRUE',
                'fecha_pago': '2026-01-06',
                'analizado': 'FALSE',
                'fecha_analisis': '',
                'porcentaje_viabilidad': '',
                'pdf_url': '',
                'aprobado': 'FALSE',
                'fecha_aprobacion': '',
                'enviado_cliente': 'FALSE',
                'fecha_envio': '',
                'notas_experto': ''
            },
            {
                'fecha': '2026-01-05',
                'hora': '14:20:00',
                'nombre': 'Ana García',
                'email': 'ana@example.com',
                'telefono': '523339876543',
                'marca': 'CAFETERÍA LUNA',
                'descripcion': 'Cafetería y servicios de alimentos',
                'tipo_negocio': 'Servicios',
                'clase_sugerida': '43',
                'status_impi': 'SIMILAR',
                'pagado': 'FALSE',
                'fecha_pago': '',
                'analizado': 'FALSE',
                'fecha_analisis': '',
                'porcentaje_viabilidad': '',
                'pdf_url': '',
                'aprobado': 'FALSE',
                'fecha_aprobacion': '',
                'enviado_cliente': 'FALSE',
                'fecha_envio': '',
                'notas_experto': ''
            },
            {
                'fecha': '2026-01-04',
                'hora': '16:45:00',
                'nombre': 'Luis Martínez',
                'email': 'luis@example.com',
                'telefono': '523335551234',
                'marca': 'TECH INNOVATE',
                'descripcion': 'Desarrollo de software',
                'tipo_negocio': 'Tecnología',
                'clase_sugerida': '42',
                'status_impi': 'DISPONIBLE',
                'pagado': 'TRUE',
                'fecha_pago': '2026-01-05',
                'analizado': 'TRUE',
                'fecha_analisis': '2026-01-05 18:30:00',
                'porcentaje_viabilidad': '75',
                'pdf_url': 'https://drive.google.com/file/d/ejemplo123',
                'aprobado': 'TRUE',
                'fecha_aprobacion': '2026-01-05 19:00:00',
                'enviado_cliente': 'TRUE',
                'fecha_envio': '2026-01-05 19:05:00',
                'notas_experto': 'Buena viabilidad, pocas marcas similares'
            }
        ]
        
        logger.warning("⚠️ Usando MockGoogleSheetsClient - Datos de prueba")
    
    def obtener_leads(self, filtro: Optional[str] = None, limite: Optional[int] = None) -> List[Dict]:
        """Retorna leads mock según el filtro"""
        
        leads = self.leads_mock.copy()
        
        if filtro == 'pagados':
            leads = [l for l in leads if l['pagado'] == 'TRUE']
        elif filtro == 'no_pagados':
            leads = [l for l in leads if l['pagado'] == 'FALSE']
        elif filtro == 'analizados':
            leads = [l for l in leads if l['analizado'] == 'TRUE']
        elif filtro == 'pendientes':
            leads = [l for l in leads if l['pagado'] == 'TRUE' and l['analizado'] == 'FALSE']
        
        if limite:
            leads = leads[:limite]
        
        logger.info(f"📋 Mock: Retornando {len(leads)} leads (filtro: {filtro})")
        return leads
    
    def obtener_lead_por_email(self, email: str) -> Optional[Dict]:
        """Retorna lead mock por email"""
        for lead in self.leads_mock:
            if lead['email'] == email:
                return lead
        return None
    
    def actualizar_lead(self, email: str, campos: Dict) -> bool:
        """Simula actualización"""
        logger.info(f"📝 Mock: Actualizaría lead {email} con campos: {list(campos.keys())}")
        return True
    
    def marcar_analizado(self, email: str, porcentaje_viabilidad: int, pdf_url: Optional[str] = None) -> bool:
        logger.info(f"✅ Mock: Marcaría como analizado: {email} ({porcentaje_viabilidad}%)")
        return True
    
    def marcar_aprobado(self, email: str, aprobado: bool = True) -> bool:
        logger.info(f"✅ Mock: Marcaría como aprobado: {email}")
        return True
    
    def marcar_enviado(self, email: str, pdf_url: str) -> bool:
        logger.info(f"📧 Mock: Marcaría como enviado: {email}")
        return True
    
    def agregar_nota_experto(self, email: str, nota: str) -> bool:
        logger.info(f"📝 Mock: Agregaría nota a: {email}")
        return True
    
    def obtener_estadisticas(self) -> Dict:
        return {
            'total': len(self.leads_mock),
            'pagados': sum(1 for l in self.leads_mock if l['pagado'] == 'TRUE'),
            'no_pagados': sum(1 for l in self.leads_mock if l['pagado'] == 'FALSE'),
            'analizados': sum(1 for l in self.leads_mock if l['analizado'] == 'TRUE'),
            'pendientes': sum(1 for l in self.leads_mock if l['pagado'] == 'TRUE' and l['analizado'] == 'FALSE')
        }
