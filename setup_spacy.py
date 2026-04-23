import subprocess
import sys


def modello_spacy_installato():
    try:
        import spacy
        spacy.load("it_core_news_sm")
        print("[OK] Modello spaCy italiano gia installato")
        return True
    except Exception:
        return False


if not modello_spacy_installato():
    print("[INSTALL] Scarico modello spaCy italiano...")
    subprocess.run([
        sys.executable, "-m", "spacy", "download", "it_core_news_sm"
    ], check=True)
    print("[OK] Modello spaCy italiano installato")
else:
    print("[SKIP] spaCy italiano gia presente, salto")
