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
    def descargar_juego(self):
        """Verifica la versión remota y descarga/extrae el ZIP si hay actualización."""
        try:
            remote = requests.get(REMOTE_VERSION_URL).json()
        except Exception as e:
            return f"Error al obtener la versión remota: {e}"

        local = load_local_version()

        if remote.get("game_version") and local.get("game_version") != remote.get("game_version"):
            version = remote.get("game_version")
            print(f"Nueva versión del juego detectada: {version}")
            zip_path = GAME_DATA / "game.zip"
            try:
                download_file(remote.get("game_url"), zip_path)
            except Exception as e:
                return f"Error al descargar ZIP: {e}"

            #if remote.get("game_hash") and sha256_file(zip_path) != remote.get("game_hash"):
            #    return "Hash juego inválido"

            # borrar contenido anterior
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

            # extraer y borrar zip
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
            return f"Juego actualizado a {version}"
        else:
            return "No hay actualizaciones"


def start():
    print("Core iniciado.")

    html_path = LAUNCHER_DATA / "index.html"
    print("HTML PATH:", html_path)

    api = LauncherAPI()
    webview.create_window(
        "PF Launcher",
        str(html_path),
        width=600,
        height=800,
        resizable=False,
        frameless=True,
        background_color='#000000',
        js_api=api,
    )
    webview.start()

if __name__ == "__main__":
    start()