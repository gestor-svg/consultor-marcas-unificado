import os
import time
import json
import re
from datetime import datetime
from functools import lru_cache
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import google.generativeai as genai

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "clave-super-secreta-cambiar-en-produccion")

# --- CONFIGURACIÓN ---
API_KEY_GEMINI = os.environ.get("API_KEY_GEMINI")
PASSWORD_INTERNA = os.environ.get("PASSWORD_INTERNA", "marcasegura2025")  # Cambiar en producción

if API_KEY_GEMINI:
    genai.configure(api_key=API_KEY_GEMINI)
    print("✓ Gemini configurado")

# --- FUNCIONES AUXILIARES ---

def normalizar_marca(marca):
    """Normaliza el nombre de la marca"""
    marca = marca.upper().strip()
    marca = re.sub(r'[^\w\s\-]', '', marca)
    marca = re.sub(r'\s+', ' ', marca)
    return marca

@lru_cache(maxsize=100)
def clasificar_con_gemini(descripcion, tipo_negocio):
    """Usa Gemini para determinar la clase de Niza"""
    if not API_KEY_GEMINI:
        return {
            "clase_principal": "35",
            "clase_nombre": "Servicios comerciales",
            "clases_adicionales": [],
            "nota": "IA no disponible"
        }
    
    try:
        model = genai.GenerativeModel('gemini-2.5-flash')
        
        prompt = f"""Eres un experto en clasificación de marcas según el sistema de Niza de la OMPI.

Analiza este negocio:
- Descripción: {descripcion}
- Tipo: {tipo_negocio}

Responde ÚNICAMENTE con un objeto JSON válido (sin markdown):
{{
  "clase_principal": "XX",
  "clase_nombre": "Descripción corta de la clase",
  "clases_adicionales": ["YY", "ZZ"],
  "nota": "Breve explicación de por qué esta clase"
}}

Recuerda:
- Productos: Clases 1-34
- Servicios: Clases 35-45
- Sé específico y preciso"""

        response = model.generate_content(
            prompt,
            generation_config=genai.GenerationConfig(
                temperature=0.3,
                max_output_tokens=512,
            )
        )
        
        text = response.text.strip()
        
        # Limpiar markdown y extraer JSON
        if "```" in text:
            parts = text.split("```")
            for part in parts:
                if '{' in part:
                    text = part.replace("json", "").replace("JSON", "").strip()
                    break
        
        # Limpiar y extraer JSON válido
        text = text.replace('\n', ' ').replace('\r', '').strip()
        start = text.find('{')
        end = text.rfind('}') + 1
        
        if start >= 0 and end > start:
            text = text[start:end]
        
        resultado = json.loads(text)
        print(f"[GEMINI] Clase sugerida: {resultado['clase_principal']}")
        return resultado
        
    except Exception as e:
        print(f"[ERROR GEMINI] {e}")
        if tipo_negocio.lower() == 'producto':
            return {
                "clase_principal": "9",
                "clase_nombre": "Productos tecnológicos",
                "clases_adicionales": ["35"],
                "nota": "Clasificación por defecto"
            }
        else:
            return {
                "clase_principal": "35",
                "clase_nombre": "Servicios comerciales",
                "clases_adicionales": ["42"],
                "nota": "Clasificación por defecto"
            }

def buscar_impi_selenium_fonetico(marca, clase_niza):
    """
    Búsqueda FONÉTICA en IMPI usando Selenium
    VERSIÓN INTERNA - Búsqueda completa y profesional
    Retorna: diccionario con resultados detallados
    """
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    import shutil

# Detectar ruta de Chrome automáticamente
chrome_binary = shutil.which("google-chrome-stable") or shutil.which("google-chrome") or "/usr/bin/google-chrome-stable"
chrome_options.binary_location = chrome_binary
    
    driver = None
    resultado = {
        "status": "ERROR",
        "cantidad_resultados": 0,
        "marcas_encontradas": [],
        "mensaje": "",
        "tiempo_busqueda": 0
    }
    
    try:
        inicio = time.time()
        marca_norm = normalizar_marca(marca)
        print(f"\n[SELENIUM] Iniciando búsqueda fonética: '{marca_norm}' en Clase {clase_niza}")
        
        driver = webdriver.Chrome(options=chrome_options)
        driver.set_page_load_timeout(40)
        
        # URL de búsqueda fonética
        url = "https://acervomarcas.impi.gob.mx:8181/marcanet/vistas/common/datos/bsqFoneticaCompleta.pgi"
        driver.get(url)
        
        wait = WebDriverWait(driver, 25)
        
        # Esperar formulario
        input_denominacion = wait.until(EC.presence_of_element_located((By.NAME, "denominacion")))
        input_clase = driver.find_element(By.NAME, "clase")
        
        # Llenar formulario
        input_denominacion.clear()
        input_denominacion.send_keys(marca_norm)
        
        input_clase.clear()
        input_clase.send_keys(str(clase_niza))
        
        # Buscar botón y hacer clic
        btn_buscar = wait.until(EC.element_to_be_clickable((By.ID, "btnBuscar")))
        driver.execute_script("arguments[0].click();", btn_buscar)
        
        print(f"[SELENIUM] Búsqueda enviada, esperando resultados...")
        time.sleep(8)  # Esperar respuesta del IMPI
        
        # Analizar resultados
        source = driver.page_source
        soup = BeautifulSoup(source, 'html.parser')
        
        if "no se encontraron registros" in source.lower() or "sin resultados" in source.lower():
            resultado["status"] = "DISPONIBLE"
            resultado["mensaje"] = f"No se encontraron marcas similares a '{marca}' en la Clase {clase_niza}"
            print(f"[SELENIUM] ✓ Marca aparentemente disponible")
            
        else:
            # Buscar tabla de resultados
            tablas = soup.find_all('table', {'class': ['tabla', 'resultados']})
            if not tablas:
                tablas = soup.find_all('table')
            
            marcas_encontradas = []
            
            for tabla in tablas:
                filas = tabla.find_all('tr')[1:]  # Saltar encabezado
                
                for fila in filas:
                    celdas = fila.find_all('td')
                    if len(celdas) >= 3:
                        marca_similar = {
                            "denominacion": celdas[0].get_text(strip=True) if len(celdas) > 0 else "",
                            "expediente": celdas[1].get_text(strip=True) if len(celdas) > 1 else "",
                            "status": celdas[2].get_text(strip=True) if len(celdas) > 2 else "",
                            "titular": celdas[3].get_text(strip=True) if len(celdas) > 3 else "",
                            "clase": celdas[4].get_text(strip=True) if len(celdas) > 4 else clase_niza
                        }
                        marcas_encontradas.append(marca_similar)
            
            if marcas_encontradas:
                resultado["status"] = "SIMILARES_ENCONTRADAS"
                resultado["cantidad_resultados"] = len(marcas_encontradas)
                resultado["marcas_encontradas"] = marcas_encontradas
                resultado["mensaje"] = f"Se encontraron {len(marcas_encontradas)} marcas similares"
                print(f"[SELENIUM] ✗ {len(marcas_encontradas)} marcas similares encontradas")
            else:
                resultado["status"] = "VERIFICAR_MANUAL"
                resultado["mensaje"] = "Resultados ambiguos, requiere verificación manual"
                print(f"[SELENIUM] ? Resultado incierto")
        
        resultado["tiempo_busqueda"] = round(time.time() - inicio, 2)
        
    except Exception as e:
        print(f"[SELENIUM] Error: {e}")
        resultado["status"] = "ERROR"
        resultado["mensaje"] = f"Error al consultar IMPI: {str(e)}"
        
    finally:
        if driver:
            driver.quit()
    
    return resultado

# --- RUTAS ---

@app.route('/')
def home():
    if 'logged_in' not in session:
        return redirect(url_for('login'))
    return render_template('index_interna.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        password = request.form.get('password', '')
        if password == PASSWORD_INTERNA:
            session['logged_in'] = True
            session['login_time'] = datetime.now().isoformat()
            return redirect(url_for('home'))
        else:
            return render_template('login.html', error="Contraseña incorrecta")
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/analizar', methods=['POST'])
def analizar():
    """
    Endpoint de análisis - VERSIÓN INTERNA
    Usa Selenium con búsqueda fonética completa
    """
    if 'logged_in' not in session:
        return jsonify({"error": "No autorizado"}), 401
    
    data = request.json
    marca = data.get('marca', '').strip()
    descripcion = data.get('descripcion', '').strip()
    tipo_negocio = data.get('tipo', 'servicio').lower()
    
    if not marca or not descripcion:
        return jsonify({"error": "Marca y descripción son obligatorias"}), 400
    
    print(f"\n{'='*70}")
    print(f"ANÁLISIS PROFESIONAL - Versión Interna")
    print(f"Marca: {marca}")
    print(f"Tipo: {tipo_negocio}")
    print(f"Usuario: {session.get('logged_in')}")
    print(f"{'='*70}")
    
    # 1. Clasificar con Gemini
    clasificacion = clasificar_con_gemini(descripcion, tipo_negocio)
    
    # 2. Búsqueda completa en IMPI con Selenium
    resultado_impi = buscar_impi_selenium_fonetico(marca, clasificacion['clase_principal'])
    
    # 3. Preparar respuesta completa
    respuesta = {
        "marca": marca,
        "tipo_negocio": tipo_negocio,
        "descripcion": descripcion,
        "clasificacion": clasificacion,
        "impi": resultado_impi,
        "fecha_analisis": datetime.now().isoformat(),
        "recomendacion": generar_recomendacion(resultado_impi, clasificacion)
    }
    
    print(f"[RESULTADO] Status: {resultado_impi['status']}, Marcas: {resultado_impi['cantidad_resultados']}")
    print(f"{'='*70}\n")
    
    return jsonify(respuesta)

def generar_recomendacion(resultado_impi, clasificacion):
    """Genera recomendación profesional basada en resultados"""
    if resultado_impi['status'] == "DISPONIBLE":
        return {
            "nivel_riesgo": "BAJO",
            "color": "green",
            "texto": "La marca aparenta estar disponible. Se recomienda proceder con el registro.",
            "pasos_siguientes": [
                f"Verificar también en clases adicionales: {', '.join(clasificacion.get('clases_adicionales', []))}",
                "Realizar búsqueda de imágenes similares si aplica",
                "Preparar documentación para solicitud de registro",
                "Considerar registro defensivo en clases relacionadas"
            ]
        }
    elif resultado_impi['status'] == "SIMILARES_ENCONTRADAS":
        cantidad = resultado_impi['cantidad_resultados']
        return {
            "nivel_riesgo": "ALTO" if cantidad > 5 else "MEDIO",
            "color": "red" if cantidad > 5 else "orange",
            "texto": f"Se encontraron {cantidad} marcas similares. Alto riesgo de rechazo.",
            "pasos_siguientes": [
                "Analizar cada marca similar individualmente",
                "Verificar vigencia de los registros encontrados",
                "Considerar variación significativa de la denominación",
                "Evaluar estrategia de coexistencia si es posible",
                "Consultar con cliente sobre alternativas de nombre"
            ]
        }
    else:
        return {
            "nivel_riesgo": "MEDIO",
            "color": "orange",
            "texto": "Se requiere análisis manual adicional en el portal del IMPI.",
            "pasos_siguientes": [
                "Realizar búsqueda manual en Marcanet",
                "Verificar en sistema MARCia",
                "Consultar expedientes específicos",
                "Análisis de distintividad y registrabilidad"
            ]
        }

@app.route('/historial')
def historial():
    """Ver historial de búsquedas (por implementar)"""
    if 'logged_in' not in session:
        return jsonify({"error": "No autorizado"}), 401
    # Por implementar: conexión a BD para historial
    return jsonify({"mensaje": "Historial por implementar"})

@app.route('/health')
def health():
    return jsonify({
        "status": "ok",
        "version": "interna-1.0",
        "gemini": bool(API_KEY_GEMINI),
        "selenium": True,
        "autenticacion": bool(PASSWORD_INTERNA)
    })

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10001))
    print(f"\n{'='*70}")
    print(f"🔐 CONSULTOR DE MARCAS - VERSIÓN INTERNA")
    print(f"{'='*70}")
    print(f"Puerto: {port}")
    print(f"Gemini: {'✓' if API_KEY_GEMINI else '✗'}")
    print(f"Selenium: ✓ (Búsqueda fonética completa)")
    print(f"Password: {'✓ Configurado' if PASSWORD_INTERNA else '✗ NO configurado'}")
    print(f"{'='*70}\n")
    app.run(host='0.0.0.0', port=port, debug=False)
