import subprocess
import sys
import platform
import urllib.request
import os


def install_ollama():
    sistema = platform.system()
    print(f"[SETUP] Sistema rilevato: {sistema}")

    if sistema == "Windows":
        print("[SETUP] Download Ollama per Windows...")
        url = "https://ollama.com/download/OllamaSetup.exe"
        dest = os.path.join(os.environ.get("TEMP", "C:\\Temp"), "OllamaSetup.exe")
        urllib.request.urlretrieve(url, dest)
        print("[SETUP] Avvio installazione silenziosa...")
        subprocess.run([dest, "/S"], check=True)
        print("[SETUP] Ollama installato su Windows")

    elif sistema == "Darwin":
        print("[SETUP] Installazione Ollama su macOS...")
        subprocess.run(
            "curl -fsSL https://ollama.com/install.sh | sh",
            shell=True,
            check=True,
        )
        print("[SETUP] Ollama installato su macOS")

    elif sistema == "Linux":
        print("[SETUP] Installazione Ollama su Linux...")
        subprocess.run(
            "curl -fsSL https://ollama.com/install.sh | sh",
            shell=True,
            check=True,
        )
        print("[SETUP] Ollama installato su Linux")

    else:
        print(f"[ERRORE] Sistema non supportato: {sistema}")
        sys.exit(1)


install_ollama()
