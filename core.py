import webview
from pathlib import Path

def start():
    print("Core iniciado.")

    base_path = Path.cwd()
    html_path = base_path / "launcher_data" / "index.html"
    print("HTML PATH:", html_path)
    webview.create_window("PF Launcher", str(html_path))
    webview.start()

if __name__ == "__main__":
    start()