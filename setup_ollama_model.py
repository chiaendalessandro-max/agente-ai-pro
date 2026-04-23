import subprocess
import time
import sys
import requests


def _ollama_cmd() -> list[str]:
    try:
        subprocess.run(["ollama", "--version"], capture_output=True, check=True, text=True)
        return ["ollama"]
    except Exception:
        import platform
        if platform.system() == "Windows":
            user = subprocess.check_output("whoami", shell=True).decode().strip().split("\\")[-1]
            return [rf"C:\Users\{user}\AppData\Local\Programs\Ollama\ollama.exe"]
        return ["ollama"]


def avvia_ollama():
    print("[SETUP] Avvio Ollama in background...")
    cmd = _ollama_cmd()
    try:
        subprocess.Popen(
            cmd + ["serve"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        time.sleep(4)
        print("[SETUP] Ollama avviato")
    except FileNotFoundError:
        print("[ERRORE] Ollama non trovato nel PATH. Riprovo con percorso completo...")
        import platform
        if platform.system() == "Windows":
            percorso = r"C:\Users\{}\AppData\Local\Programs\Ollama\ollama.exe".format(
                subprocess.check_output("whoami", shell=True).decode().strip().split("\\")[-1]
            )
            subprocess.Popen([percorso, "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            time.sleep(4)


def verifica_ollama():
    print("[SETUP] Verifico che Ollama risponda...")
    for tentativo in range(10):
        try:
            r = requests.get("http://localhost:11434/api/tags", timeout=3)
            if r.status_code == 200:
                print("[SETUP] Ollama risponde correttamente")
                return True
        except Exception:
            pass
        print(f"[SETUP] Attendo Ollama... tentativo {tentativo+1}/10")
        time.sleep(2)
    print("[ERRORE] Ollama non risponde dopo 10 tentativi")
    return False


def scarica_modello():
    print("[SETUP] Download modello llama3 (puo richiedere qualche minuto)...")
    cmd = _ollama_cmd()
    result = subprocess.run(
        cmd + ["pull", "llama3"],
        capture_output=False,
        text=True
    )
    if result.returncode == 0:
        print("[SETUP] Modello llama3 scaricato con successo")
    else:
        print("[SETUP] llama3 fallito, provo con mistral (piu leggero)...")
        subprocess.run(cmd + ["pull", "mistral"], check=True)
        print("[SETUP] Modello mistral scaricato con successo")


avvia_ollama()
if verifica_ollama():
    scarica_modello()
else:
    sys.exit(1)
