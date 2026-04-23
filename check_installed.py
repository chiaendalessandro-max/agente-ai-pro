import importlib
import subprocess
import sys

PACCHETTI = {
    "requests":               "requests",
    "bs4":                    "beautifulsoup4",
    "lxml":                   "lxml",
    "ollama":                 "ollama",
    "pandas":                 "pandas",
    "spacy":                  "spacy",
    "sentence_transformers":  "sentence-transformers",
    "sklearn":                "scikit-learn",
    "pandasai":               "pandasai",
    "torch":                  "torch",
}

da_installare = []

print("=" * 50)
print("VERIFICA DIPENDENZE")
print("=" * 50)

for modulo, pacchetto in PACCHETTI.items():
    try:
        importlib.import_module(modulo)
        print(f"[OK] GIA INSTALLATO: {pacchetto}")
    except ImportError:
        print(f"[NO] MANCANTE:     {pacchetto}")
        da_installare.append(pacchetto)

print(f"\nDa installare: {len(da_installare)} pacchetti")
print(da_installare)

# Salva lista per step successivo
with open("da_installare.txt", "w") as f:
    f.write("\n".join(da_installare))
