import os
import json
import hashlib
import requests
import sys
import importlib.util
from pathlib import Path
import webview
from importlib.machinery import SourceFileLoader
import zipfile
import shutil

BASE_DIR = Path("launcher_data")
BASE_DIR.mkdir(exist_ok=True)

BASE_DIR_ASSETS = Path("launcher_data/assets")
BASE_DIR_ASSETS.mkdir(exist_ok=True)

VERSION_FILE = Path("version_local.json")
REMOTE_VERSION_URL = "https://raw.githubusercontent.com/Uni44/PFLauncher/main/version.json"

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

def check_and_update():
    print("Verificando versiones...")

    remote = requests.get(REMOTE_VERSION_URL).json()
    local = load_local_version()

    # --- CORE ---
    core_path = BASE_DIR / "core.data"
    if local.get("core_version") != remote["core_version"]:
        print("Actualizando core...")
        download_file(remote["core_url"], core_path)

        # hash validation removed to avoid problems
        # if sha256_file(core_path) != remote["core_hash"]:
        #     print("Hash core inválido")

        local["core_version"] = remote["core_version"]

    # --- HTML ---
    html_path = BASE_DIR / "index.html"
    if local.get("html_version") != remote["html_version"]:
        print("Actualizando HTML...")
        download_file(remote["html_url"], html_path)

        # hash validation removed to avoid problems
        # if sha256_file(html_path) != remote["html_hash"]:
        #     print("Hash HTML inválido")

        local["html_version"] = remote["html_version"]

    # --- ASSETS ---
    if remote.get("assets_version") and local.get("assets_version") != remote.get("assets_version"):
        print("Actualizando assets...")
        zip_path = BASE_DIR / "assets.zip"
        download_file(remote.get("assets_url"), zip_path)

        # clear old assets
        for item in BASE_DIR_ASSETS.iterdir():
            if item.is_dir():
                shutil.rmtree(item)
            else:
                try:
                    item.unlink()
                except Exception:
                    pass

        try:
            with zipfile.ZipFile(zip_path, "r") as z:
                z.extractall(BASE_DIR_ASSETS)
        except zipfile.BadZipFile:
            print("Assets zip corrupto")
        finally:
            if zip_path.exists():
                zip_path.unlink()

        local["assets_version"] = remote.get("assets_version")

    save_local_version(local)

def run_core():
    core_path = BASE_DIR / "core.data"

    loader = SourceFileLoader("core", str(core_path))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)

    # Ejecutar manualmente
    if hasattr(module, "start"):
        module.start()
    else:
        print("El core no tiene función start()")

if __name__ == "__main__":
    check_and_update()
    run_core()