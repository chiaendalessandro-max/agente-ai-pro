import logging
logging.basicConfig(level=logging.INFO, format="%(message)s")

print("=" * 55)
print("TEST PIPELINE AI ANALISI DATI")
print("=" * 55)

# Test spaCy
print("\n[TEST 1] spaCy — Estrazione entità...")
try:
    from ai_data_analysis import estrai_aziende_da_testo
    testo = "Alitalia SPA e Airbus Italia sono tra le principali aziende aeronautiche italiane. Leonardo SpA opera nel settore difesa."
    risultato = estrai_aziende_da_testo(testo)
    print(f"[OK] spaCy OK - Estratte: {risultato}")
except Exception as e:
    print(f"[WARN] spaCy: {e}")

# Test deduplicazione
print("\n[TEST 2] Deduplicazione intelligente...")
try:
    from ai_data_analysis import deduplica_intelligente
    test_aziende = [
        {"name": "Alitalia SPA"},
        {"name": "Alitalia S.p.A."},
        {"name": "Leonardo SpA"},
        {"name": "Leonardo S.p.A."},
        {"name": "Airbus Italia"},
    ]
    uniche = deduplica_intelligente(test_aziende)
    print(f"[OK] Dedup OK - {len(test_aziende)} -> {len(uniche)} aziende")
except Exception as e:
    print(f"[WARN] Dedup: {e}")

# Test classificazione
print("\n[TEST 3] Classificazione per rilevanza...")
try:
    from ai_data_analysis import classifica_per_rilevanza
    test = [
        {"name": "AirItaly", "description": "compagnia aerea italiana"},
        {"name": "Fiat Auto", "description": "produttore automobili"},
        {"name": "VistaJet", "description": "jet privati lusso"},
    ]
    classificate = classifica_per_rilevanza(test, "private jet", "Italia")
    print(f"[OK] Rank OK - Prima azienda: {classificate[0]['name']} (score: {classificate[0].get('relevance_score','N/A')})")
except Exception as e:
    print(f"[WARN] Rank: {e}")

# Test Ollama
print("\n[TEST 4] Ollama AI locale...")
try:
    from ai_data_analysis import ollama_disponibile, analizza_azienda_con_ai
    if ollama_disponibile():
        result = analizza_azienda_con_ai("VistaJet", "Operatore jet privati di lusso", "private jet")
        print(f"[OK] Ollama OK - Analisi: {result}")
    else:
        print("[WARN] Ollama non attivo - avvia setup_ollama_auto.py")
except Exception as e:
    print(f"[WARN] Ollama: {e}")

print("\n" + "=" * 55)
print("TEST COMPLETATO")
print("=" * 55)
