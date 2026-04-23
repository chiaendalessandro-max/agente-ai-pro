import subprocess
import time
import sys
import requests
import platform


def ollama_gia_attivo():
    try:
        requests.get("http://localhost:11434/api/tags", timeout=2)
        return True
    except Exception:
        return False


def avvia_ollama_background():
    if ollama_gia_attivo():
        print("[START] Ollama gia attivo")
        return True

    print("[START] Avvio Ollama in background...")
    sistema = platform.system()

    try:
        if sistema == "Windows":
            subprocess.Popen(
                ["ollama", "serve"],
                creationflags=subprocess.CREATE_NO_WINDOW
            )
        else:
            subprocess.Popen(
                ["ollama", "serve"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )

        for i in range(15):
            time.sleep(2)
            if ollama_gia_attivo():
                print("[START] Ollama pronto")
                return True
            print(f"[START] Attendo Ollama... {i+1}/15")

        print("[WARNING] Ollama non risponde, continuo senza AI")
        return False

    except FileNotFoundError:
        print("[WARNING] Ollama non installato, continuo senza AI")
        return False


if __name__ == "__main__":
    avvia_ollama_background()
    print("[START] Sistema pronto. Avvio applicazione principale...")
    # Avvia qui la tua applicazione principale
    # subprocess.run([sys.executable, "main.py"])
