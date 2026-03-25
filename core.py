import webview
from pathlib import Path
import requests
import json
import hashlib
import zipfile
import shutil
import subprocess
import threading
#import pystray
#from PIL import Image, ImageDraw

REMOTE_VERSION_URL = "https://raw.githubusercontent.com/Uni44/PFLauncher/main/version.json"
BASE_DIR = Path.cwd()
LAUNCHER_DATA = BASE_DIR / "launcher_data"
GAME_DATA = BASE_DIR / "game_data"
VERSION_FILE = BASE_DIR / "version_local.json"
LAUNCHER_DATA.mkdir(exist_ok=True)
GAME_DATA.mkdir(exist_ok=True)

#def create_image():
#    img = Image.new('RGB', (64, 64), color=(0, 0, 0))
#    d = ImageDraw.Draw(img)
#    d.rectangle((16, 16, 48, 48), fill=(255, 255, 255))
#    return img

#def setup_tray(api):
#    def show_window(icon, item):
#        if api._window:
#            try:
#                api._window.restore()
#            except Exception:
#                pass
#    def exit_app(icon, item):
#        icon.stop()
#        if api._window:
#            api._window.destroy()
#    icon = pystray.Icon(
#        "pf_launcher",
#        create_image(),
#        "PF Launcher",
#        menu=pystray.Menu(
#            pystray.MenuItem("Abrir", show_window),
#            pystray.MenuItem("Salir", exit_app)
#        )
#    )
#    icon.run()

def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            h.update(chunk)
    return h.hexdigest()

def download_file(url, dest):
    r = requests.get(url)
    r.raise_for_status()
    with open(dest, "wb") as f:
        f.write(r.content)

def load_local_version():
    if VERSION_FILE.exists():
        with open(VERSION_FILE, "r") as f:
            return json.load(f)
    return {}

def save_local_version(data):
    with open(VERSION_FILE, "w") as f:
        json.dump(data, f, indent=4)

class LauncherAPI:
    def __init__(self, window=None):
        print("LauncherAPI inicializada")
        self._window = window

    def _log(self, key, progress=None, **kwargs):
        """
        Enviamos una 'key' en lugar de texto plano. 
        kwargs permite pasar variables (como la versión) si fuera necesario.
        """
        if self._window:
            # Pasamos la key y cualquier dato extra como JSON
            data = json.dumps({"key": key, "vars": kwargs})
            self._window.evaluate_js(f"updateUIStatus({data});")
            if progress is not None:
                self._window.evaluate_js(f"setProgress({progress});")
        else:
            print(msg)

    # window control API exposed to JS
    def cerrar(self):
        if self._window:
            self._window.destroy()
        return "cerrando"

    def minimizar(self):
        if self._window:
            try:
                self._window.minimize()
            except Exception:
                pass
        return "minimizado"

    # game status / launcher
    def verificar_estado(self):
        """Devuelve diccionario JSON con información de instalación y versión."""
        print("verificar_estado llamado")
        local = load_local_version()
        installed = False
        exe_path = None
        
        local_version = local.get("game_version")
        
        # if there's a saved game version, consider it installed
        if local_version:
            installed = True
        
        # look for an .exe in game_data (including subdirectories)
        if GAME_DATA.exists():
            for p in GAME_DATA.glob("**/*.exe"):
                exe_path = str(p)
                installed = True
                break
        
        # check remote version
        try:
            remote = requests.get(REMOTE_VERSION_URL).json()
            remote_version = remote.get("game_version")
        except Exception as e:
            remote_version = None
            print(f"Error fetching remote version: {e}")
        
        needs_update = remote_version and local_version and remote_version != local_version
        
        result = {
            "installed": installed,
            "version": local_version,
            "remote_version": remote_version,
            "needs_update": needs_update,
            "exe": exe_path,
        }
        
        # log for debugging
        print(f"verificar_estado: {result}")
        
        return json.dumps(result)

    def abrir_juego(self):
        for p in GAME_DATA.glob("*.exe"):
            try:
                proc = subprocess.Popen([str(p), "-source=launcher"])
                def monitor():
                    proc.wait()
                    exit_code = proc.returncode
                    if exit_code != 0:
                        self._log("game_crashed", code=exit_code)
                        self._window.restore()
                    else:
                        self._log("game_closed")
                        cerrar = self.analizar_log()
                        if cerrar:
                            self.cerrar()
                        else:
                            self._window.restore()
                threading.Thread(target=monitor, daemon=True).start()
                self._window.minimize()
                return "lanzado"
            except Exception as e:
                return f"error al abrir: {e}"
        return "no encontrado"
        
    def analizar_log(self):
        log_path = GAME_DATA / "log.txt"
        if not log_path.exists():
            return True
        try:
            with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
                lineas = f.readlines()
            errores = ["error", "exception", "fatal", "crash", "failed"]
            for i, linea in enumerate(reversed(lineas)):
                linea_low = linea.lower()
                if any(e in linea_low for e in errores):
                    idx_real = len(lineas) - 1 - i
                    inicio = max(0, idx_real - 2)
                    fin = min(len(lineas), idx_real + 5)
                    contexto = "".join(lineas[inicio:fin])
                    self._log("game_error", detail=contexto)
                    return False
            return True
        except Exception as ex:
            print(f"Error leyendo log: {ex}")
            return True

    def descargar_juego(self):
        """Verifica la versión remota y descarga/extrae el ZIP si hay actualización."""
        try:
            remote = requests.get(REMOTE_VERSION_URL, timeout=5).json()
        except Exception as e:
            local = load_local_version()
            # Si no hay internet pero el juego está instalado, permitir continuar
            if local.get("game_version"):
                self._log("error_internet")
                return "Sin conexión, usando versión local"
            # Si no hay internet y el juego no está instalado, error
            return f"Error de conexión: sin internet. {e}"

        local = load_local_version()

        if remote.get("game_version") and local.get("game_version") != remote.get("game_version"):
            version = remote.get("game_version")
            self._log("status_updating", version=version)

            zip_path = GAME_DATA / "game.zip"

            # stream download so we can report progress
            try:
                resp = requests.get(remote.get("game_url"), stream=True, timeout=10)
                resp.raise_for_status()
                total = resp.headers.get("Content-Length")
                total = int(total) if total is not None else None

                downloaded = 0
                with open(zip_path, "wb") as f:
                    for chunk in resp.iter_content(1024 * 1024):
                        if not chunk:
                            continue
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total:
                            # Calculamos Megas (Bytes / 1024 / 1024)
                            mb_descargados = round(downloaded / (1024 * 1024), 2)
                            mb_totales = round(total / (1024 * 1024), 2)
                            pct = int(downloaded / total * 100)
                            pct = int(downloaded / total * 100)
                            self._log("status_downloading", progress=pct, current=mb_descargados, total=mb_totales)
                        else:
                            pct = None
            except Exception as e:
                return f"Error al descargar ZIP: {e}"

            PROTECTED_NAMES = {
                "world",
                "worlds",
                "save",
                "saves",
                "playerdata",
                "userdata"
            }

            def is_protected(path):
                return any(part.lower() in PROTECTED_NAMES for part in path.parts)

            def safe_delete(path):
                if is_protected(path):
                    return
            
                if path.is_file():
                    path.unlink(missing_ok=True)
                    return
            
                if path.is_dir():
                    for sub in path.iterdir():
                        safe_delete(sub)
            
                    # intentar borrar la carpeta si quedó vacía
                    try:
                        path.rmdir()
                    except Exception:
                        pass
            
            for item in GAME_DATA.iterdir():
                if item == zip_path:
                    continue
                safe_delete(item)

            try:
                with zipfile.ZipFile(zip_path, 'r') as z:
                    z.extractall(GAME_DATA)
            except zipfile.BadZipFile:
                return "Error: archivo zip corrupto"
            finally:
                if zip_path.exists():
                    zip_path.unlink()

            local["game_version"] = version
            save_local_version(local)
            # notify UI to enable play
            self._log("status_updated", version=version)
            self._window.evaluate_js("setPlayMode();")
            return f"Juego actualizado a {version}"
        else:
            return "No hay actualizaciones"

    def empaquetarDev(self):
        try:
            source_dir = GAME_DATA / "ProyectoFurry_Data" / "world" / "dev"
            
            if not source_dir.exists():
                print("No existe world dev")
                return "No existe world dev"

            zip_path = BASE_DIR / "dev.zip"

            # borrar zip anterior si existe
            if zip_path.exists():
                zip_path.unlink()

            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as z:
                for file in source_dir.rglob("*"):
                    if file.is_file():
                        # ruta relativa dentro del zip
                        arcname = file.relative_to(source_dir.parent)
                        z.write(file, arcname)

            return f"ZIP creado en {zip_path}"

        except Exception as e:
            print(f"Error: {e}")
            return f"Error: {e}"

    def enviar_reporte_crash(self, crashOrError):
        log_path = GAME_DATA / "log.txt"
        try:
            mensaje = f"{crashOrError}"
            if log_path.exists():
                with open(log_path, "rb") as f:
                    requests.post(
                        "https://discord.com/api/webhooks/1486253978474774690/n_xE7LwUPWWwWoTislqa5N8FQjftuXONks-l3TB2VSxuD7VgRcuWXD70he2Izhp_usZk",
                        data={"content": mensaje},
                        files={"file": ("log.txt", f, "text/plain; charset=utf-8")}
                    )
        except Exception as e:
            print(f"Error enviando crash: {e}")

def start():
    print("Core iniciado.")

    html_path = LAUNCHER_DATA / "index.html"
    print("HTML PATH:", html_path)

    # Calcular posición central de la pantalla
    import tkinter as tk
    root = tk.Tk()
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()
    root.destroy()
    
    window_width = 1200
    window_height = 700
    x = (screen_width - window_width) // 2
    y = (screen_height - window_height) // 2

    api = LauncherAPI()
    window = webview.create_window(
        "PF Launcher",
        str(html_path),
        width=window_width,
        height=window_height,
        x=x,
        y=y,
        resizable=False,
        frameless=True,
        background_color='#000000',
        js_api=api,
    )
    # give api a reference to the window so it can send logs/progress callbacks
    api._window = window
    # iniciar tray en hilo separado
    #threading.Thread(target=setup_tray, args=(api,), daemon=True).start()
    webview.start()

if __name__ == "__main__":
    start()