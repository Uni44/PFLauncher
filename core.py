import webview
from pathlib import Path
import requests
import json
import hashlib
import zipfile
import shutil

REMOTE_VERSION_URL = "https://raw.githubusercontent.com/Uni44/PFLauncher/main/version.json"
BASE_DIR = Path.cwd()
LAUNCHER_DATA = BASE_DIR / "launcher_data"
GAME_DATA = BASE_DIR / "game_data"
VERSION_FILE = BASE_DIR / "version_local.json"

LAUNCHER_DATA.mkdir(exist_ok=True)
GAME_DATA.mkdir(exist_ok=True)

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

    def _log(self, msg, progress=None):
        """helper to send messages back to HTML logger"""
        if self._window:
            escaped = json.dumps(msg)
            self._window.evaluate_js(f"log({escaped});")
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
        """Lanza el ejecutable del juego si existe."""
        for p in GAME_DATA.glob("*.exe"):
            try:
                # Windows: use startfile
                import os
                os.startfile(str(p))
                # Cerrar launcher después de abrir el juego
                if self._window:
                    self._window.destroy()
                return "lanzado"
            except Exception as e:
                return f"error al abrir: {e}"
        return "no encontrado"

    def descargar_juego(self):
        """Verifica la versión remota y descarga/extrae el ZIP si hay actualización."""
        try:
            remote = requests.get(REMOTE_VERSION_URL, timeout=5).json()
        except Exception as e:
            local = load_local_version()
            # Si no hay internet pero el juego está instalado, permitir continuar
            if local.get("game_version"):
                self._log("Sin conexión a internet, usando versión local")
                return "Sin conexión, usando versión local"
            # Si no hay internet y el juego no está instalado, error
            return f"Error de conexión: sin internet. {e}"

        local = load_local_version()

        if remote.get("game_version") and local.get("game_version") != remote.get("game_version"):
            version = remote.get("game_version")
            self._log(f"Nueva versión del juego detectada: {version}")

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
                            pct = int(downloaded / total * 100)
                        else:
                            pct = None
                        self._log(f"Descargados {downloaded} bytes", pct)
            except Exception as e:
                return f"Error al descargar ZIP: {e}"

            # actualizar y extraer
            for item in GAME_DATA.iterdir():
                if item == zip_path:
                    continue
                if item.is_dir():
                    shutil.rmtree(item)
                else:
                    try:
                        item.unlink()
                    except Exception:
                        pass

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
            self._log(f"Juego actualizado a {version}")
            self._window.evaluate_js("setPlayMode();")
            return f"Juego actualizado a {version}"
        else:
            return "No hay actualizaciones"


def start():
    print("Core iniciado.")

    html_path = LAUNCHER_DATA / "index.html"
    print("HTML PATH:", html_path)

    api = LauncherAPI()
    window = webview.create_window(
        "PF Launcher",
        str(html_path),
        width=1200,
        height=700,
        resizable=False,
        frameless=True,
        background_color='#000000',
        js_api=api,
    )
    # give api a reference to the window so it can send logs/progress callbacks
    api._window = window
    webview.start()

if __name__ == "__main__":
    start()