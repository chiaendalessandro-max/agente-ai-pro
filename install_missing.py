import subprocess
import sys
import os

# Leggi lista pacchetti mancanti
if not os.path.exists("da_installare.txt"):
    print("[OK] Nessun pacchetto da installare")
    sys.exit(0)

with open("da_installare.txt") as f:
    da_installare = [l.strip() for l in f.readlines() if l.strip()]

if not da_installare:
    print("[OK] Tutto gia installato")
    sys.exit(0)

print(f"[INSTALL] Installo {len(da_installare)} pacchetti mancanti...")

for pacchetto in da_installare:
    print(f"\n[INSTALL] -> {pacchetto}")
    try:
        # torch ha bisogno di versione CPU per essere leggero
        if pacchetto == "torch":
            subprocess.run([
                sys.executable, "-m", "pip", "install",
                "torch", "--index-url",
                "https://download.pytorch.org/whl/cpu"
            ], check=True)
        else:
            subprocess.run([
                sys.executable, "-m", "pip", "install", pacchetto
            ], check=True)
        print(f"[OK] {pacchetto} installato")
    except subprocess.CalledProcessError as e:
        print(f"[WARNING] {pacchetto} fallito: {e} - continuo con gli altri")

print("\n[INSTALL] Completato")
