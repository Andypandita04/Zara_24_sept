



import os
import json
import time
from urllib.parse import urlparse, urlunparse
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

NOMBRE = input("Introduce un nombre para el archivo URLS: ").strip()
direccion = input("Introduce la DIRECCIÓN (ej: NIÑA, NIÑO, MUJER, etc): ").strip()
seccion = input("Introduce la SECCIÓN (ej: Niños 4-10 | Niñas 1/2 - 6 | N/A): ").strip()
SAVE_PATH = os.getcwd()
os.makedirs("logs", exist_ok=True)
if not NOMBRE:
    NOMBRE = "urls_zara"
if not NOMBRE.lower().endswith(".json"):
    NOMBRE += ".json"
JSON_PATH = os.path.join(SAVE_PATH, "logs", NOMBRE)

entrada_datos = []
while True:
    url = input("Introduce la URL de la categoría de Zara (o deja vacío para terminar): ").strip()
    if url == "":
        break
    gpo_articulo = input("Introduce el GPO_ARTICULO (ej: CAMISAS Y BLUSAS): ").strip()
    entrada_datos.append({
        "url": url,
        "gpo_articulo": gpo_articulo
    })


def obtener_urls(driver, pause_time=5, max_wait=10):
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


resultados = {
    "DIRECCION": direccion,
    "SECCION": seccion,
    "URLS": []
}


def guardar_resultados():
    with open(JSON_PATH, "w", encoding="utf-8") as archivo:
        json.dump(resultados, archivo, ensure_ascii=False, indent=2)

options = webdriver.ChromeOptions()
options.add_argument("--start-maximized")
options.add_experimental_option("debuggerAddress", "127.0.0.1:9222")
driver = webdriver.Chrome(options=options)

for entrada in entrada_datos:

    URL_BASE = entrada["url"]
    GPO_ARTICULO = entrada["gpo_articulo"]


    print(f"\nScrapeando: {GPO_ARTICULO} de {direccion} → {URL_BASE}")
    driver.get(URL_BASE)

    try:
        WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "button.onetrust-close-btn-handler"))
        ).click()
    except:
        pass

    urls_raw = obtener_urls(driver)
    urls = deduplicar_urls(urls_raw)
    resultados["URLS"].append({
        "URL_BASE": URL_BASE,
        "GPO.ARTICULO": GPO_ARTICULO,
        "URLS": urls
    })
    guardar_resultados()
    print(f"→ URLs recolectadas: {len(urls_raw)} → Productos únicos: {len(urls)}")

driver.quit()
print(f"\nJSON guardado en: {JSON_PATH}")
