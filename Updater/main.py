import requests
import sys
import time
import os

url = sys.argv[1]

print("Descargando nueva versión...")
data = requests.get(url).content

# Esperar a que el launcher cierre
time.sleep(2)

with open("Launcher_new.exe", "wb") as f:
    f.write(data)

# Reemplazo
os.remove("Launcher.exe")
os.rename("Launcher_new.exe", "Launcher.exe")

print("Actualización completa")

# Relanzar
os.startfile("Launcher.exe")