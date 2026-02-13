import os
import json
import hashlib
import requests
import importlib.util
from pathlib import Path

BASE_DIR = Path("app")
BASE_DIR.mkdir(exist_ok=True)

VERSION_FILE = Path("version_local.json")
REMOTE_VERSION_URL = "https://raw.githubusercontent.com/Uni44/PFLauncher/refs/heads/main/version.json"


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
    core_path = BASE_DIR / "core.py"
    if local.get("core_version") != remote["core_version"]:
        print("Actualizando core...")
        download_file(remote["core_url"], core_path)

        if sha256_file(core_path) != remote["core_hash"]:
            raise Exception("Hash core inválido")

        local["core_version"] = remote["core_version"]

    # --- HTML ---
    html_path = BASE_DIR / "index.html"
    if local.get("html_version") != remote["html_version"]:
        print("Actualizando HTML...")
        download_file(remote["html_url"], html_path)

        if sha256_file(html_path) != remote["html_hash"]:
            raise Exception("Hash HTML inválido")

        local["html_version"] = remote["html_version"]

    save_local_version(local)


def run_core():
    core_path = BASE_DIR / "core.py"
    spec = importlib.util.spec_from_file_location("core", core_path)
    core = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(core)


if __name__ == "__main__":
    check_and_update()
    run_core()