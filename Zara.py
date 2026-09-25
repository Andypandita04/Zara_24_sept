
# En esta primera parte, el script importa todas las librerías necesarias y define variables globales para la ejecución.

# In[1]:
import os
import time
import json
import re
import pandas as pd
import subprocess
from urllib.parse import urlparse, urlunparse
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

NOMBRE = input("Introduce un nombre para el archivo de salida (ej: Zara_Niñas_FW2026): ").strip()
SAVE_PATH = os.getcwd()
os.makedirs("logs", exist_ok=True)
FECHA_SCRAPING = datetime.today().strftime('%Y-%m-%d')

# El script es interactivo. Antes de empezar a navegar, le pide al usuario que introduzca las URLs de las categorías que desea analizar, junto con metadatos como la DIRECCIÓN (ej: MUJER) y el GPO_ARTICULO (ej: VESTIDOS Y MONOS).
# 1. Usa un bucle while True para permitir al usuario añadir múltiples categorías.
# 2. El bucle termina cuando el usuario presiona "Enter" sin introducir una URL.
# 3. Cada categoría se guarda como un diccionario en la lista entrada_datos.

# In[2]:
entrada_datos = []
while True:
    url = input("Introduce la URL de la categoría de Zara (o deja vacío para terminar): ").strip()
    if url == "":
        break
    direccion = input("Introduce la DIRECCIÓN (ej: NIÑA, NIÑO, MUJER, etc): ").strip()
    seccion = input("Introduce la SECCIÓN (ej: Niños 4-10 | Niñas 1/2 - 6 | N/A): ").strip()
    gpo_articulo = input("Introduce el GPO_ARTICULO (ej: CAMISAS Y BLUSAS): ").strip()
    entrada_datos.append({
        "url": url,
        "direccion": direccion,
        "seccion": seccion,
        "gpo_articulo": gpo_articulo
    })

print(f"\nTotal de categorías a scrapear: {len(entrada_datos)}\n")

# In[3]:
CHECKPOINT_PATH = os.path.join(SAVE_PATH, "logs", f"{NOMBRE}_checkpoint.json")

if os.path.exists(CHECKPOINT_PATH):
    try:
        with open(CHECKPOINT_PATH, "r", encoding="utf-8") as checkpoint_file:
            checkpoint = json.load(checkpoint_file)
        if not isinstance(checkpoint, dict):
            checkpoint = {}
    except (json.JSONDecodeError, OSError):
        checkpoint = {}
else:
    checkpoint = {}

productos_escaneados = set(checkpoint.get("productos_escaneados", []))
checkpoint["productos_escaneados"] = list(productos_escaneados)
checkpoint["filas"] = checkpoint.get("filas", [])


def guardar_checkpoint():
    filas_actuales = df.to_dict(orient="records") if "df" in globals() else []
    filas_guardadas = checkpoint.get("filas", [])
    filas_nuevas = [fila for fila in filas_actuales if fila not in filas_guardadas]
    checkpoint["filas"] = filas_guardadas + filas_nuevas
    checkpoint["productos_escaneados"] = sorted(productos_escaneados)
    checkpoint["ultima_actualizacion"] = datetime.now().isoformat(timespec="seconds")
    with open(CHECKPOINT_PATH, "w", encoding="utf-8") as checkpoint_file:
        json.dump(checkpoint, checkpoint_file, ensure_ascii=False, indent=2)


if not os.path.exists(CHECKPOINT_PATH):
    guardar_checkpoint()

print(
    f"Checkpoint cargado: {len(productos_escaneados)} productos ya escaneados, "
    f"{len(checkpoint['filas'])} filas guardadas"
)

# Esta función maneja el scroll infinito de las páginas de categoría de Zara.
# 1. Hace scroll hasta el final de la página repetidamente.
# 2. Después de cada scroll, busca los enlaces a los productos y los añade a un set para evitar duplicados.
# 3. La función es inteligente: detecta cuando la altura de la página deja de aumentar después de varios intentos, lo que significa que todos los productos han sido cargados, y entonces se detiene.

# In[4]:
def obtener_urls(driver, pause_time=2, max_wait=5):
    urls = set()
    prev_height = driver.execute_script("return document.body.scrollHeight")
    same_count_rounds = 0

    while True:
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(pause_time)

        links = driver.find_elements(By.CSS_SELECTOR, "li.product-grid-product a.product-link")
        for link in links:
            href = link.get_attribute("href")
            if href:
                urls.add(href.strip())

        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == prev_height:
            same_count_rounds += 1
        else:
            same_count_rounds = 0
            prev_height = new_height

        if same_count_rounds >= max_wait:
            break

    return list(urls)

def deduplicar_urls(urls):
    vistos = set()
    unicas = []
    for url in urls:
        parsed = urlparse(url)
        url_limpia = urlunparse((parsed.scheme, parsed.netloc, parsed.path, '', '', ''))
        if url_limpia not in vistos:
            vistos.add(url_limpia)
            unicas.append(url_limpia)
    return unicas

# Transformar cadenas de texto no estructuradas (ej: "$1,299.00 MXN") en valores numéricos procesables, eliminando caracteres especiales y símbolos de moneda.

# In[5]:
def limpiar_precio(p):
    return int(p.replace('$', '').replace(',', '').replace('.00', '').strip())

def limpiar_color(color):
    # Sustituye el patron del SKU (4 digitos/3 digitos/3 digitos) por una cadena vacia
    return re.sub(r'\s*\d{4}/\d{3}/\d{3}\s*$', '', color).strip()

def limpiar_descripcion(descripcion):
    descripcion = re.sub(
        r'\s*Altura\s+modelo\s*:\s*\d+\s*cm\s*',
        ' ',
        descripcion,
        flags=re.IGNORECASE
    )
    return ' '.join(descripcion.split())

# Extrae la composición del tejido del producto.
# 1. En Zara, esta información está oculta y requiere hacer clic en un botón para mostrarse.
# 2. El código identifica y hace clic en el botón correcto.
# 3. Una vez visible la información, utiliza Selenium para parsear el HTML y extraer el texto de manera limpia, juntando las diferentes líneas en un solo string.

# In[6]:
def extraer_composicion(driver):
    try:
        elem = driver.find_element(
            By.CSS_SELECTOR,
            "div.product-detail-composition.product-detail-view__detailed-composition" #main > div > div > div > div.product-detail-view-std > article > div.product-detail-view__secondary-content > div > div
        )
        texto = elem.text.strip()
        if ":" in texto:
            texto = texto.split(":", 1)[1].strip()
        return texto if texto else "N/A"
    except Exception as e:
        print(f"Error composición: {e}")
        return "N/A"

# En esta parte del script, donde se procesa cada producto y sus variantes.
# 1. Inicialización: Se crea una instancia del navegador Chrome y un DataFrame de Pandas vacío.
# 2. Bucle por Categoría: El script itera sobre cada URL que el usuario proporcionó.
# 3. Gestión de Pop-ups: Al entrar en una categoría, intenta cerrar las ventanas de cookies y cambiar la vista de la cuadrícula de productos para asegurar que todos los elementos carguen correctamente.
# 4. Recolección de URLs: Llama a obtener_urls() para obtener la lista de todos los productos de la categoría.
# 
# En lugar de buscar cada dato (nombre, descripción) en un elemento HTML diferente, aprovecha que Zara incrusta una etiqueta $<script>$ que contiene un objeto JSON con toda la información del producto.
# 
# 5. Bucle por Producto: Itera sobre la URL de cada producto encontrado.
# 6. Lectura del JSON:
# 
#     -Navega a la página del producto.
# 
#     -Localiza la etiqueta $<script type="application/ld+json">$.
#     
#     -Extrae su contenido de texto y lo convierte de un string a un diccionario de Python usando json.loads(). Esto le da acceso inmediato y estructurado al nombre, descripción, SKU, etc.
# 
# 7. Bucle por Variante de Color:
# 
#     -Detecta cuántos botones de selección de color hay en la página.
# 
#     -Itera sobre cada color, haciendo clic en su botón correspondiente.
# 
#     -Importante: Después de cada clic, espera a que la página se actualice y vuelve a leer el JSON, que ahora contendrá la información específica de la variante de color seleccionada (como el SKU y la imagen).
# 
# 8. Extracción de Datos Híbrida:
# 
#     -Obtiene la mayoría de los datos del diccionario JSON (prod_data).
# 
#     -Obtiene datos que no están en el JSON o son más fáciles de obtener visualmente (como el precio o la composición) usando los métodos tradicionales de Selenium.
# 9. Almacenamiento y Manejo de Errores:
# 
#     -Crea un diccionario con todos los datos extraídos de una variante.
# 
#     -Añade este diccionario como una nueva fila al DataFrame df.
#     
#     -Si algo falla, guarda el error en el diccionario fallos y continúa con el siguiente producto, evitando que el script se detenga.

# In[7]:
df = pd.DataFrame()
fallos = {}

options = webdriver.ChromeOptions()
options.add_argument("--start-maximized")
driver = webdriver.Chrome(options=options)

for entrada in entrada_datos:

    URL_BASE = entrada["url"]
    DIRECCION = entrada["direccion"]
    GPO_ARTICULO = entrada["gpo_articulo"]
    SECCION = entrada.get("seccion", "N/A")

    print(f"\nScrapeando: {GPO_ARTICULO} de {DIRECCION} → {URL_BASE}")
    driver.get(URL_BASE)

    try:
        WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "button.onetrust-close-btn-handler"))
        ).click()
    except:
        pass

    urls_raw = obtener_urls(driver)
    urls = deduplicar_urls(urls_raw)
    print(f"→ URLs recolectadas: {len(urls_raw)} → Productos únicos: {len(urls)}")

    for url in urls:
        if url in productos_escaneados:
            print(f"   Producto ya escaneado, se omite: {url}")
            continue

        try:
            driver.get(url)

            WebDriverWait(driver, 20).until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, "button.product-color-extended-name__copy-action")
                )
            )

            driver.execute_script("window.scrollTo(0, document.body.scrollHeight/3);")
            time.sleep(3)

            try:
                WebDriverWait(driver, 5).until(
                    EC.presence_of_all_elements_located(
                        (By.CSS_SELECTOR, "button.product-detail-color-item__color-button")
                    )
                )
            except:
                pass

            color_buttons = driver.find_elements(
                By.CSS_SELECTOR,
                "button.product-detail-color-item__color-button"
            )

            total_colores = len(color_buttons) if color_buttons else 1
            print(f"   Colores encontrados: {total_colores}")

            imagen_url_anterior = None
            try:
                img_el = driver.find_element(
                    By.CSS_SELECTOR,
                    "div.media-core.product-detail-image__image img.ecs-media-picture__image"
                )
                imagen_url_anterior = img_el.get_attribute("src")
            except:
                pass

            for i in range(total_colores):
                try:
                    color_buttons = driver.find_elements(
                        By.CSS_SELECTOR,
                        "button.product-detail-color-item__color-button"
                    )

                    if total_colores > 1:
                        try:
                            img_pre = driver.find_element(
                                By.CSS_SELECTOR,
                                "div.media-core.product-detail-image__image img.ecs-media-picture__image"
                            )
                            img_src_antes = img_pre.get_attribute("src")
                        except:
                            img_src_antes = None

                        driver.execute_script(
                            "arguments[0].scrollIntoView({block: 'center'});",
                            color_buttons[i]
                        )
                        time.sleep(0.5)
                        driver.execute_script(
                            "arguments[0].click();",
                            color_buttons[i]
                        )

                        WebDriverWait(driver, 5).until(
                            EC.presence_of_element_located(
                                (By.CSS_SELECTOR, "p.product-color-extended-name")
                            )
                        )

                        driver.execute_script("window.scrollTo(0, 0);")
                        time.sleep(1)

                        if img_src_antes:
                            try:
                                WebDriverWait(driver, 10).until(
                                    lambda d: d.find_element(
                                        By.CSS_SELECTOR,
                                        "div.media-core.product-detail-image__image img.ecs-media-picture__image"
                                    ).get_attribute("src") != img_src_antes
                                )
                            except TimeoutException:
                                pass

                        time.sleep(1)

                    composicion = extraer_composicion(driver)

                    try:
                        imagenes = driver.find_elements(
                            By.CSS_SELECTOR,
                            "div.media-core.product-detail-image__image img.ecs-media-picture__image"
                        )
                        imagen_url = "N/A"
                        for img in imagenes:
                            src = img.get_attribute("src")
                            if src and "transparent" not in src and "data:" not in src:
                                imagen_url = src
                                break
                        if imagen_url == "N/A" and imagenes:
                            imagen_url = imagenes[0].get_attribute("src") or "N/A"
                    except:
                        imagen_url = "N/A"

                    try:
                        SKU_COMPLETO = driver.find_element(
                            By.CSS_SELECTOR,
                            "button.product-color-extended-name__copy-action"
                        ).text.strip()
                    except:
                        SKU_COMPLETO = "N/A"

                    try:
                        color = driver.find_element(
                            By.CSS_SELECTOR,
                            "p.product-color-extended-name"
                        ).text.split("|")[0].strip()
                        color = limpiar_color(color)
                    except:
                        color = "N/A"

                    PRECIO_ORIGINAL = "N/A"
                    PRECIO_DESCUENTO = "N/A"

                    try:
                        precio_actual_element = driver.find_element(
                            By.CSS_SELECTOR,
                            '[data-qa-qualifier="price-amount-current"] .money-amount__main'
                        )
                        precio_actual = f"${limpiar_precio(precio_actual_element.text.strip())}"
                    except:
                        precio_actual = "N/A"

                    try:
                        precio_original_element = driver.find_element(
                            By.CSS_SELECTOR,
                            '[data-qa-qualifier="price-amount-old"] .money-amount__main'
                        )
                        PRECIO_ORIGINAL = f"${limpiar_precio(precio_original_element.text.strip())}"
                        PRECIO_DESCUENTO = precio_actual
                    except:
                        PRECIO_ORIGINAL = precio_actual

                    try:
                        PRODUCTO = driver.find_element(
                            By.CSS_SELECTOR,
                            "h1.product-detail-info__header-name"
                        ).text.strip()
                    except:
                        PRODUCTO = "N/A"

                    try:
                        descripcion = driver.find_element(
                            By.CSS_SELECTOR,
                            'meta[name="description"]'
                        ).get_attribute("content")
                        descripcion = limpiar_descripcion(descripcion or "")
                    except:
                        descripcion = "N/A"

                    partes_sku = SKU_COMPLETO.split("/")
                    SKU_GENERICO = "/".join(partes_sku[:2]) if len(partes_sku) >= 2 else SKU_COMPLETO

                    fila = {
                        "FECHA": FECHA_SCRAPING,
                        "TEMPORADA" : "FW | 2026",
                        "SITIO": "ZARA",
                        "DIRECCION": DIRECCION,
                        "SECCION" : SECCION,
                        "GPO. ARTICULO": GPO_ARTICULO,
                        "PRODUCTO": PRODUCTO,
                        "SKU VARIANTE": SKU_COMPLETO,
                        "SKU GENÉRICO": SKU_GENERICO,
                        "PRECIO ORIGINAL": PRECIO_ORIGINAL,
                        "PRECIO DESCUENTO": PRECIO_DESCUENTO,
                        "COLOR": color,
                        "DESCRIPCIÓN": descripcion,
                        "COMPOSICIÓN": composicion,
                        "URL": url,
                        "IMAGEN": imagen_url
                    }

                    df = pd.concat([df, pd.DataFrame([fila])], ignore_index=True)
                    print(f"      Color procesado: {color}")
                    print(fila)

                except Exception as e:
                    print(f"Error en color {i+1} → {e}")
                    continue

            productos_escaneados.add(url)
            guardar_checkpoint()
            print(f"   Checkpoint guardado: {url}")

        except Exception as e:
            print(f"ERROR en producto {url} → {e}")
            continue

# Al terminar de procesar todas las categorías, el script concluye:
# 1. Organiza las Columnas: Reordena las columnas del DataFrame para un resultado limpio y consistente.
# 2. Exporta a Excel: Guarda el DataFrame en un archivo .xlsx.
# 3. Registra Errores: Guarda cualquier error capturado en un archivo .json en la carpeta logs.
# 4. Abre el Resultado: Abre automáticamente el archivo Excel para que el usuario pueda revisarlo de inmediato.
# 5. Cierra el Navegador: Libera los recursos cerrando la ventana de Chrome.

# In[8]:
column_order = [
    "FECHA", "TEMPORADA", "SITIO", "DIRECCION", "SECCION", "GPO. ARTICULO", "PRODUCTO",
    "SKU GENÉRICO", "SKU VARIANTE", "PRECIO ORIGINAL", "PRECIO DESCUENTO",
    "COLOR", "DESCRIPCIÓN", "COMPOSICIÓN", "URL", "IMAGEN"
]

if checkpoint.get("filas"):
    df = pd.DataFrame(checkpoint["filas"])

if not df.empty:
    df = df[column_order]

    excel_path = os.path.join(SAVE_PATH, f"{NOMBRE}_{FECHA_SCRAPING}.xlsx")
    df.to_excel(excel_path, index=False)

    print(f"\nArchivo guardado en: {excel_path}")
    subprocess.Popen(['start', excel_path], shell=True)