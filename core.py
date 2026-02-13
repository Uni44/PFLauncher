import webview

def start():
    webview.create_window("Launcher", "launcher_data/index.html")
    webview.start()

if __name__ == "__main__":
    start()