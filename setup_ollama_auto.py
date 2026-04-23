import subprocess
import sys
import time
import platform
import urllib.request
import os


def _ollama_cmd():
    try:
        subprocess.run(["ollama", "--version"], capture_output=True, check=True)
        return ["ollama"]
    except Exception:
        if platform.system() == "Windows":
            user = os.environ.get("USERNAME", "")
            candidate = rf"C:\Users\{user}\AppData\Local\Programs\Ollama\ollama.exe"
            if os.path.exists(candidate):
                return [candidate]
        return ["ollama"]


def ollama_risponde():
    try:
        import requests
        requests.get("http://localhost:11434/api/tags", timeout=3)
        return True
    except Exception:
        return False


def ollama_installato():
    try:
        subprocess.run(_ollama_cmd() + ["--version"],
                      capture_output=True, check=True)
        return True
    except Exception:
        return False


def installa_ollama():
    sistema = platform.system()
    print(f"[INSTALL] Installazione Ollama su {sistema}...")
    if sistema in ("Darwin", "Linux"):
        subprocess.run(
            "curl -fsSL https://ollama.com/install.sh | sh",
            shell=True, check=True
        )
    elif sistema == "Windows":
        dest = os.path.join(os.environ.get("TEMP", "C:\\Temp"), "OllamaSetup.exe")
        urllib.request.urlretrieve("https://ollama.com/download/OllamaSetup.exe", dest)
        subprocess.run([dest, "/S"], check=True)
        time.sleep(5)
    print("[OK] Ollama installato")


def avvia_ollama():
    print("[START] Avvio Ollama in background...")
    sistema = platform.system()
    cmd = _ollama_cmd()
    if sistema == "Windows":
        subprocess.Popen(cmd + ["serve"],
                        creationflags=subprocess.CREATE_NO_WINDOW)
    else:
        subprocess.Popen(cmd + ["serve"],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL)
    for i in range(15):
        time.sleep(2)
        if ollama_risponde():
            print("[OK] Ollama pronto")
            return True
        print(f"[WAIT] Attendo Ollama... {i+1}/15")
    return False


def scarica_modello():
    import requests
    cmd = _ollama_cmd()
    r = requests.get("http://localhost:11434/api/tags", timeout=5)
    modelli_presenti = [m["name"].split(":")[0]
                       for m in r.json().get("models", [])]
    print(f"[INFO] Modelli gia presenti: {modelli_presenti}")
    for modello in ["llama3", "mistral", "phi3", "gemma2"]:
        if modello in modelli_presenti:
            print(f"[SKIP] Modello {modello} gia scaricato")
            return modello
    print("[INSTALL] Scarico mistral (modello leggero)...")
    subprocess.run(cmd + ["pull", "mistral"], check=True)
    return "mistral"


# - Esecuzione -
if not ollama_installato():
    installa_ollama()

if not ollama_risponde():
    avvia_ollama()
else:
    print("[SKIP] Ollama gia attivo, salto avvio")

modello = scarica_modello()
print(f"[OK] Modello attivo: {modello}")

with open("ollama_model.txt", "w") as f:
    f.write(modello)
