





import json
import os
import time
import pandas as pd

"""
Recupera los datos de un archivo JSON y los convierte a un archivo Excel.
"""
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
        with open(CHECKPOINT_PATH, "r", encoding="utf-8") as archivo:
            datos = json.load(archivo)
            if isinstance(datos,dict):
                print(f"Se cargo el diccionario de {entrada}.json")
            else:
                print(f"El contenido de {entrada}.json no es un diccionario")
    except Exception as e:  
        print(f"Error al cargar el archivo {entrada}.json: {e}")
else:
    print(f"El archivo {entrada}.json no existe.")

filas = datos.get("filas", [])
productos_escaneados = datos.get("productos_escaneados", [])

if not isinstance(filas, list):
    raise ValueError("El campo 'filas' debe ser una lista")
if not isinstance(productos_escaneados, list):
    productos_escaneados = list(productos_escaneados)

urls_anteriores = set(productos_escaneados)
cont = 0
for fila in filas:
    if not isinstance(fila, dict):
        continue

    url = fila.get("URL")
    if url:
        cont += 1
        if url not in urls_anteriores:
            productos_escaneados.append(url)
            urls_anteriores.add(url)
            print(f"Se agrego la url {url} a productos_escaneados")
        else:
            print(f"La url {cont} : {url} ya estaba en productos_escaneados")

datos["productos_escaneados"] = productos_escaneados
datos["ultima_actualizacion"] = time.strftime("%Y-%m-%dT%H:%M:%S")

with open(CHECKPOINT_PATH, "w", encoding="utf-8") as archivo:
    json.dump(datos, archivo, ensure_ascii=False, indent=2)
    
    

    









