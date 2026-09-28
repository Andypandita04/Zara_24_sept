import os
import re
import json
import time
import subprocess
from datetime import datetime
from urllib.parse import urlparse, urlunparse

import pandas as pd
from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


def limpiar_precio(p):
    if p is None:
        return 0
    texto = str(p).replace('$', '').replace(',', '').replace('.00', '').strip()
    try:
        return int(texto)
    except ValueError:
        return 0


def limpiar_color(color):
    return re.sub(r'\s*\d{4}/\d{3}/\d{3}\s*$', '', color or '').strip()


def limpiar_descripcion(descripcion):
    descripcion = re.sub(
        r'\s*Altura\s+modelo\s*:\s*\d+\s*cm\s*',
        ' ',
        descripcion or '',
        flags=re.IGNORECASE,
    )
    return ' '.join(descripcion.split())


def extraer_composicion(driver):
    try:
        elem = driver.find_element(
            By.CSS_SELECTOR,
            "div.product-detail-composition.product-detail-view__detailed-composition"
        )
        texto = elem.text.strip()
        if ":" in texto:
            texto = texto.split(":", 1)[1].strip()
        return texto if texto else "N/A"
    except Exception:
        return "N/A"


def cargar_json_urls(ruta_json):
    with open(ruta_json, "r", encoding="utf-8") as archivo:
        datos = json.load(archivo)

    entradas = []

    if isinstance(datos, dict):
        items = datos.get("URLS", [])
        if isinstance(items, list):
            for item in items:
                if not isinstance(item, dict):
                    continue
                url_base = item.get("URL_BASE") or item.get("URL") or item.get("url") or "N/A"
                gpo = (
                    item.get("GPO.ARTICULO")
                    or item.get("GPO_ARTICULO")
                    or item.get("gpo_articulo")
                    or "N/A"
                )
                urls = item.get("URLS", [])
                if isinstance(urls, list):
                    for url in urls:
                        if url:
                            entradas.append({
                                "url": url,
                                "gpo_articulo": gpo,
                                "url_base": url_base,
                            })
                elif isinstance(item.get("URL"), str):
                    entradas.append({
                        "url": item["URL"],
                        "gpo_articulo": gpo,
                        "url_base": url_base,
                    })
        elif isinstance(datos.get("url"), str):
            entradas.append({
                "url": datos["url"],
                "gpo_articulo": datos.get("gpo_articulo", "N/A"),
                "url_base": datos.get("url", "N/A"),
            })

    elif isinstance(datos, list):
        for item in datos:
            if isinstance(item, dict):
                if "URLS" in item and isinstance(item["URLS"], list):
                    for url in item["URLS"]:
                        entradas.append({
                            "url": url,
                            "gpo_articulo": item.get("GPO.ARTICULO") or item.get("GPO_ARTICULO") or "N/A",
                            "url_base": item.get("URL_BASE") or "N/A",
                        })
                elif isinstance(item.get("url"), str):
                    entradas.append({
                        "url": item["url"],
                        "gpo_articulo": item.get("gpo_articulo", "N/A"),
                        "url_base": item.get("url", "N/A"),
                    })
            elif isinstance(item, str):
                entradas.append({
                    "url": item,
                    "gpo_articulo": "N/A",
                    "url_base": item,
                })

    # Elimina duplicados de URL
    vistas = set()
    unicas = []
    for entrada in entradas:
        url = entrada["url"]
        parsed = urlparse(url)
        url_limpia = urlunparse((parsed.scheme, parsed.netloc, parsed.path, '', '', ''))
        if url_limpia not in vistas:
            vistas.add(url_limpia)
            unicas.append({
                "url": url_limpia,
                "gpo_articulo": entrada["gpo_articulo"],
                "url_base": entrada["url_base"],
            })
    return unicas


def procesar_producto(driver, url, direccion, seccion, gpo_articulo, fecha_scraping):
    driver.get(url)

    try:
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, "button.product-color-extended-name__copy-action")
            )
        )
    except TimeoutException:
        return None

    time.sleep(2)

    try:
        WebDriverWait(driver, 5).until(
            EC.presence_of_all_elements_located(
                (By.CSS_SELECTOR, "button.product-detail-color-item__color-button")
            )
        )
    except Exception:
        pass

    color_buttons = driver.find_elements(
        By.CSS_SELECTOR,
        "button.product-detail-color-item__color-button"
    )
    total_colores = len(color_buttons) if color_buttons else 1

    resultados = []

    for i in range(total_colores):
        try:
            color_buttons = driver.find_elements(
                By.CSS_SELECTOR,
                "button.product-detail-color-item__color-button"
            )

            if total_colores > 1:
                try:
                    img_before = driver.find_element(
                        By.CSS_SELECTOR,
                        "div.media-core.product-detail-image__image img.ecs-media-picture__image"
                    )
                    img_src_before = img_before.get_attribute("src")
                except Exception:
                    img_src_before = None

                driver.execute_script(
                    "arguments[0].scrollIntoView({block: 'center'});",
                    color_buttons[i]
                )
                time.sleep(0.5)
                driver.execute_script("arguments[0].click();", color_buttons[i])
                WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located(
                        (By.CSS_SELECTOR, "p.product-color-extended-name")
                    )
                )
                driver.execute_script("window.scrollTo(0, 0);")
                time.sleep(1)

                if img_src_before:
                    try:
                        WebDriverWait(driver, 10).until(
                            lambda d: d.find_element(
                                By.CSS_SELECTOR,
                                "div.media-core.product-detail-image__image img.ecs-media-picture__image"
                            ).get_attribute("src") != img_src_before
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
            except Exception:
                imagen_url = "N/A"

            try:
                sku_completo = driver.find_element(
                    By.CSS_SELECTOR,
                    "button.product-color-extended-name__copy-action"
                ).text.strip()
            except Exception:
                sku_completo = "N/A"

            try:
                color = driver.find_element(
                    By.CSS_SELECTOR,
                    "p.product-color-extended-name"
                ).text.split("|")[0].strip()
                color = limpiar_color(color)
            except Exception:
                color = "N/A"

            PRECIO_ORIGINAL = "N/A"
            PRECIO_DESCUENTO = "N/A"

            try:
                precio_actual_element = driver.find_element(
                    By.CSS_SELECTOR,
                    '[data-qa-qualifier="price-amount-current"] .money-amount__main'
                )
                precio_actual = f"${limpiar_precio(precio_actual_element.text.strip())}"
            except Exception:
                precio_actual = "N/A"

            try:
                precio_original_element = driver.find_element(
                    By.CSS_SELECTOR,
                    '[data-qa-qualifier="price-amount-old"] .money-amount__main'
                )
                precio_original = f"${limpiar_precio(precio_original_element.text.strip())}"
                PRECIO_ORIGINAL = precio_original
                if precio_actual != "N/A" and PRECIO_ORIGINAL == precio_actual:
                    PRECIO_DESCUENTO = "N/A"
                else:
                    PRECIO_DESCUENTO = precio_actual
            except Exception:
                precio_original = precio_actual
                PRECIO_ORIGINAL = precio_original
                PRECIO_DESCUENTO = "N/A" if precio_actual != "N/A" else "N/A"

            try:
                producto = driver.find_element(
                    By.CSS_SELECTOR,
                    "h1.product-detail-info__header-name"
                ).text.strip()
            except Exception:
                producto = "N/A"

            try:
                descripcion = driver.find_element(
                    By.CSS_SELECTOR,
                    'meta[name="description"]'
                ).get_attribute("content")
                descripcion = limpiar_descripcion(descripcion or "")
            except Exception:
                descripcion = "N/A"

            partes_sku = sku_completo.split("/")
            sku_generico = "/".join(partes_sku[:2]) if len(partes_sku) >= 2 else sku_completo

            fila = {
                "FECHA": fecha_scraping,
                "TEMPORADA": "FW | 2026",
                "SITIO": "ZARA",
                "DIRECCION": direccion,
                "SECCION": seccion,
                "GPO. ARTICULO": gpo_articulo,
                "PRODUCTO": producto,
                "SKU VARIANTE": sku_completo,
                "SKU GENÉRICO": sku_generico,
                "PRECIO ORIGINAL": precio_original,
                "PRECIO DESCUENTO": precio_actual,
                "COLOR": color,
                "DESCRIPCIÓN": descripcion,
                "COMPOSICIÓN": composicion,
                "URL": url,
                "IMAGEN": imagen_url,
            }

            resultados.append(fila)
            print(f"  [OK] {producto} | {color}")

        except Exception as e:
            print(f"  [ERROR] Color {i + 1}: {e}")
            continue

    return resultados


def main():
    save_path = os.getcwd()
    os.makedirs("logs", exist_ok=True)

    json_path = input("Introduce la ruta del JSON generado por urls_zara.py: ").strip()
    if not json_path:
        json_path = os.path.join(save_path, "logs", "urls_zara.json")
    if not os.path.isabs(json_path):
        json_path = os.path.join(save_path, json_path)
    if os.path.splitext(json_path)[1].lower() != ".json":
        json_path += ".json"

    with open(json_path, "r", encoding="utf-8") as archivo:
        json_data = json.load(archivo)

    direccion = (
        json_data.get("DIRECCION")
        or json_data.get("DIRECCION")
        or json_data.get("direccion")
        or "N/A"
    )
    seccion = (
        json_data.get("SECCION")
        or json_data.get("seccion")
        or "N/A"
    )
    output_name = input("Introduce el nombre base del archivo final (ej: Zara_Productos): ").strip() or "Zara_Productos"
    output_name = os.path.basename(output_name)
    output_name = os.path.splitext(output_name)[0]
    if not output_name:
        output_name = "Zara_Productos"
    CHECKPOINT_PATH = os.path.join(save_path, "logs", f"{output_name}.json")

    if os.path.exists(CHECKPOINT_PATH):
        try:
            with open(CHECKPOINT_PATH, "r", encoding="utf-8") as checkpoint_file:
                checkpoint = json.load(checkpoint_file)
            print(f"Checkpoint cargado desde: {CHECKPOINT_PATH}")
            if not isinstance(checkpoint, dict):
                checkpoint = {}
        except (json.JSONDecodeError, OSError):
            checkpoint = {}
    else:
        checkpoint = {}
        print(f"No se encontró checkpoint en: {CHECKPOINT_PATH}")
        respuesta = input("¿Quieres crear uno nuevo para continuar? (s/n): ").strip().lower()
        if respuesta not in {"s", "si", "y", "yes"}:
            print("Se cancela la ejecución porque no se creó el checkpoint.")
            return
        print(f"Se creará un nuevo checkpoint en: {CHECKPOINT_PATH}")

    productos_escaneados = set(checkpoint.get("productos_escaneados", []))
    checkpoint["productos_escaneados"] = list(productos_escaneados)
    checkpoint["filas"] = checkpoint.get("filas", [])

    def guardar_checkpoint(registro_nuevo=None):
        checkpoint["productos_escaneados"] = sorted(productos_escaneados)
        checkpoint["ultima_actualizacion"] = datetime.now().isoformat(timespec="seconds")
        with open(CHECKPOINT_PATH, "w", encoding="utf-8") as checkpoint_file:
            json.dump(checkpoint, checkpoint_file, ensure_ascii=False, indent=2)

        if registro_nuevo is not None:
            print(f"\n--- REGISTRO GUARDADO EN CHECKPOINT ---")
            print(json.dumps(registro_nuevo, ensure_ascii=False, indent=2))
            print(f"--- FIN REGISTRO ---\n")

    entradas = cargar_json_urls(json_path)
    if not entradas:
        raise ValueError(f"No se encontraron URLs válidas en: {json_path}")

    print(f"Metadatos del JSON -> DIRECCION: {direccion} | SECCION: {seccion}")
    print(
        f"Checkpoint cargado: {len(productos_escaneados)} productos ya escaneados, "
        f"{len(checkpoint['filas'])} filas guardadas"
    )

    fecha_scraping = datetime.today().strftime('%Y-%m-%d')
    todas_las_filas = []

    options = webdriver.ChromeOptions()
    options.add_argument("--start-maximized")
    driver = webdriver.Chrome(options=options)

    try:
        for idx, entrada in enumerate(entradas, start=1):
            url = entrada["url"]
            gpo_articulo = entrada["gpo_articulo"]

            if url in productos_escaneados:
                print(f"\n[{idx}/{len(entradas)}] Producto ya escaneado, se omite: {url}")
                continue

            print(f"\n[{idx}/{len(entradas)}] Procesando: {gpo_articulo} -> {url}")
            filas = procesar_producto(driver, url, direccion, seccion, gpo_articulo, fecha_scraping)
            if filas:
                todas_las_filas.extend(filas)
                filas_nuevas = [fila for fila in filas if fila not in checkpoint.get("filas", [])]
                checkpoint["filas"] = checkpoint.get("filas", []) + filas_nuevas
                productos_escaneados.add(url)
                guardar_checkpoint(registro_nuevo=filas_nuevas)
                print(f"   Producto registrado en checkpoint: {url}")

    finally:
        driver.quit()

    if not todas_las_filas:
        print("No se extrajo ningún registro.")
        return

    df = pd.DataFrame(checkpoint["filas"] if checkpoint.get("filas") else todas_las_filas)
    columnas = [
        "FECHA", "TEMPORADA", "SITIO", "DIRECCION", "SECCION", "GPO. ARTICULO", "PRODUCTO",
        "SKU GENÉRICO", "SKU VARIANTE", "PRECIO ORIGINAL", "PRECIO DESCUENTO",
        "COLOR", "DESCRIPCIÓN", "COMPOSICIÓN", "URL", "IMAGEN"
    ]
    df = df[columnas]

    output_excel = os.path.join(save_path, f"{output_name}_{fecha_scraping}.xlsx")
    df.to_excel(output_excel, index=False)
    print(f"\nArchivo exportado: {output_excel}")
    subprocess.Popen(["start", output_excel], shell=True)


if __name__ == "__main__":
    main()
