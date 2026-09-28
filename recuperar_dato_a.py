




import json
import os
import time
from selenium.webdriver.common.by import By
from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import pandas as pd

entrada = "Zara_Niños_FW2026_2026-09-23" #Nombre del Json
ruta_actual = os.getcwd()

CHECKPOINT_PATH = os.path.join(ruta_actual,F"{entrada}.json" )



def extraer_composicion(driver):
    try:
        elem = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((
                By.CSS_SELECTOR,
                "div.product-detail-composition.product-detail-view__detailed-composition"
            ))
        )
        texto = elem.text.strip()
        if ":" in texto:
            texto = texto.split(":", 1)[1].strip()
        return texto if texto else "N/A"
    except Exception as e:
        print(f"Error composición: {e}")
        return "N/A"


def extraer_imagen_principal(driver):
    try:
        elementos = WebDriverWait(driver, 10).until(
            EC.presence_of_all_elements_located((
                By.CSS_SELECTOR,
                "button.product-detail-card__main-image picture source[srcset], "
                "button.product-detail-card__main-image picture img, "
                "div.product-detail-card__main-image-wrapper picture source[srcset], "
                "div.product-detail-card__main-image-wrapper picture img, "
                "div.product-detail-image__image img"
            ))
        )
    except Exception as e:
        print(
            "No se pudo localizar la imagen: "
            f"title={driver.title!r}, url={driver.current_url!r}, error={type(e).__name__}"
        )
        return "N/A"

    candidatos = []
    for elemento in elementos:
        srcset = elemento.get_attribute("srcset")
        if srcset:
            for candidato in srcset.split(","):
                partes = candidato.strip().split()
                if not partes:
                    continue
                ancho = 0
                if len(partes) > 1 and partes[1].endswith("w"):
                    try:
                        ancho = int(partes[1][:-1])
                    except ValueError:
                        pass
                candidatos.append((ancho, partes[0]))

        for atributo in ("src", "data-src"):
            url = elemento.get_attribute(atributo)
            if url and not url.startswith("data:") and "transparent" not in url:
                candidatos.append((0, url))

    return max(candidatos, key=lambda candidato: candidato[0])[1] if candidatos else "N/A"


if os.path.exists(CHECKPOINT_PATH):
    try:
        with open(CHECKPOINT_PATH, "r", encoding= "utf-8" ) as archivo:
            datos = json.load(archivo)
            if isinstance(datos,dict):
                print(f"Se cargo el diccionario de {entrada}.json")
            else:
                print(f"El contenido de {entrada}.json no es un diccionario")
    except Exception as e:
        print(f"Error al cargar el archivo {entrada}.json: {e}")
else:
    print(f"El archivo {entrada}.json no existe.")

# Aqui guardo las filas del json 
filas = datos["filas"] 


#Vamos a extraer el dato faltante
options = webdriver.ChromeOptions()
options.add_argument("--start-maximized")
options.add_experimental_option("debuggerAddress", "127.0.0.1:9222")
driver = webdriver.Chrome(options=options)

try:
    for a in filas:
        if(a["IMAGEN"]=="N/A"):

            try:
                driver.get(a["URL"])
                imagen_url = extraer_imagen_principal(driver)
                if imagen_url == "N/A":
                    print("Reintentando la página después de una pausa...")
                    time.sleep(3)
                    driver.get(a["URL"])
                    imagen_url = extraer_imagen_principal(driver)

                if(imagen_url == "N/A"):
                    print(f"No se encontró una imagen válida para la URL: {a['URL']}")
                else:
                    a["IMAGEN"] = imagen_url
            except Exception as e:
                print(f"Error al acceder a la URL {a['URL']}: {e}")
            finally:
                print(f"Procesado: {a['URL']} - Imagen: {a['IMAGEN']}")

        if(a["COMPOSICIÓN"]=="N/A" ):
            a["COMPOSICIÓN"] = extraer_composicion(driver)

        if(a["PRODUCTO"]== "N/A"):
            try :
                producto = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((
                        By.CSS_SELECTOR,
                        "h1.product-detail-info__header-name"
                    ))
                )
                a["PRODUCTO"] = producto.text.strip() or "N/A"
            except Exception as e:
                print(f"Error producto: {e}")
                a["PRODUCTO"] = "N/A"
                

                
finally:
    checkpoint = {
        "filas": filas,
        "ultima_actualizacion": time.strftime("%Y-%m-%dT%H:%M:%S")
    }

    with open(CHECKPOINT_PATH, "w", encoding="utf-8") as archivo:
        json.dump(checkpoint, archivo, ensure_ascii=False, indent=2)


    #df = pd.DataFrame(filas)
    #excel_ruta = os.path.join(ruta_actual, f"{entrada}.xlsx")
    #df.to_excel(excel_ruta, index=False)
    #print(f"Archivo Excel guardado en: {excel_ruta}")

