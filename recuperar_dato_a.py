




import json
import os
import time
from selenium.webdriver.common.by import By
from selenium import webdriver
import pandas as pd

entrada = "Zara_Niños_FW2026_2026-09-23" #Nombre del Json
ruta_actual = os.getcwd()

CHECKPOINT_PATH = os.path.join(ruta_actual,F"{entrada}.json" )



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
driver = webdriver.Chrome(options=options)

try:
    for a in filas:
        if(a["IMAGEN"]=="N/A"):

            try:
                driver.get(a["URL"])
                time.sleep(3)
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
                    driver.find_element(
                            By.CSS_SELECTOR,
                            "h1.product-detail-info__header-name"
                    ).text.strip()
                except:
                    PRODUCTO = "N/A"
                

                
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

