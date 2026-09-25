


import json
import os
import pandas as pd

"""
Recupera los datos de un archivo JSON y los convierte a un archivo Excel.
"""
entrada = "Zara_Niñas_Mayores_FW2026_checkpoint"
ruta_actual = os.getcwd()
CHECKPOINT_PATH = os.path.join(ruta_actual,F"{entrada}.json" )

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

filas = datos["filas"] 

df = pd.DataFrame(filas)
excel_ruta = os.path.join(ruta_actual, f"{entrada}.xlsx")
df.to_excel(excel_ruta, index=False)
print(f"Archivo Excel guardado en: {excel_ruta}")

