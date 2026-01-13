# 🎯 Consultor de Marcas - Sistema Unificado

Sistema completo de análisis de marcas que integra:
- **🔓 Sistema PÚBLICO**: Landing page, funnel de ventas, captura de leads
- **🔐 Sistema INTERNO**: Dashboard de expertos, análisis fonético IMPI, generación de PDFs

---

## 📊 Arquitectura del Sistema

### Sistema PÚBLICO (Sin autenticación)
Funnel de ventas para captura de leads y conversión a clientes.

**Características:**
- Búsqueda IMPI por **denominación** (búsqueda simple/exacta)
- Clasificación automática de Clase de Niza con Gemini
- Integración con MercadoPago para pagos
- Notificaciones push via ntfy.sh

### Sistema INTERNO (Requiere autenticación)
Dashboard para expertos del despacho que realizan análisis completos.

**Características:**
- Búsqueda IMPI **fonética** (búsqueda exhaustiva con hasta 300 marcas)
- Análisis inteligente con Gemini 2.0 (ordena por riesgo)
- UI totalmente editable
- Generación de PDFs profesionales
- Sistema de IDs únicos

---

## 🚀 Deployment en Render

### Variables de Entorno Requeridas

```bash
# Compartidas
SECRET_KEY=tu-secret-key
API_KEY_GEMINI=tu-api-key
GOOGLE_APPS_SCRIPT_URL=https://script.google.com/macros/s/.../exec
GMAIL_USER=tu-email@gmail.com
GMAIL_PASSWORD=tu-password

# Públicas
MERCADO_PAGO_LINK=https://mpago.li/tu-link
WHATSAPP_NUMERO=52XXXXXXXXXX
CAL_COM_URL=https://cal.com/usuario/30min
APP_BASE_URL=https://tu-app.onrender.com

# Internas
ADMIN_USER=gestor
ADMIN_PASS=tu-password
```

---

## 🔑 Diferencias Clave: Búsqueda IMPI

### Búsqueda por DENOMINACIÓN (Público)
- Archivo: `impi_denominacion.py`
- Tipo: Búsqueda simple/exacta
- Uso: Análisis rápido en landing page

### Búsqueda FONÉTICA (Interno)
- Archivo: `impi_fonetico_COMPLETO.py`
- Tipo: Búsqueda exhaustiva (hasta 300 marcas)
- Uso: Análisis completo por expertos

**🚨 IMPORTANTE**: Ambos motores funcionan independientemente y NO deben modificarse.

---

## 📋 Flujo Completo

1. Usuario llena formulario público → Lead capturado en Google Sheets
2. Usuario paga ($950 MXN)
3. Experto ve lead en dashboard
4. Ejecuta análisis fonético completo
5. Revisa y edita resultado
6. Genera PDF profesional
7. PDF enviado al cliente

---

## ✅ Estado: LISTO PARA PRODUCCIÓN

**Última actualización**: Enero 13, 2026  
**Versión**: 1.0 (Unificado)
