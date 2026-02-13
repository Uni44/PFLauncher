import webview

def start():
    print("Core iniciado.")
    webview.create_window("Launcher", "launcher_data/index.html")
    webview.start()

if __name__ == "__main__":
    start()