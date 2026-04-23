import logging
import time

logging.basicConfig(level=logging.INFO, format="%(message)s")

print("=" * 50)
print("TEST SISTEMA RICERCA AZIENDE")
print("=" * 50)

print("\n[TEST 1] Verifica Ollama...")
from ai_company_helper import is_ollama_available, get_modello_disponibile

if is_ollama_available():
    modello = get_modello_disponibile()
    print(f"[OK] Ollama attivo - modello: {modello}")
else:
    print("[WARN] Ollama non attivo - ricerca funzionera solo con scraping")

print("\n[TEST 2] Ricerca aziende reali...")
from company_search_real import search_companies_real

start = time.time()
risultati = search_companies_real("private jet", "Italia", 10)
elapsed = time.time() - start

print(f"\n{'=' * 50}")
print(f"Trovate: {len(risultati)} aziende in {elapsed:.1f} secondi")
print(f"{'=' * 50}")
for i, r in enumerate(risultati):
    print(f"[{i+1:02d}] {r['name']:<45} | {r['website']}")

if len(risultati) >= 10:
    print("\n[OK] TEST SUPERATO - sistema funzionante")
else:
    print(f"\n[WARN] Trovate solo {len(risultati)} aziende, fallback necessario")
