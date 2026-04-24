import logging
import json
import os
import re
import importlib
import subprocess
import sys

logger = logging.getLogger(__name__)
_NLP = None
_SENTENCE_MODEL = None


def ensure_local_dependencies() -> dict:
    needed = {
        "spacy": "spacy",
        "sentence_transformers": "sentence-transformers",
        "sklearn": "scikit-learn",
    }
    out = {"installed": [], "failed": []}
    for mod, pkg in needed.items():
        try:
            importlib.import_module(mod)
        except Exception:
            try:
                subprocess.run([sys.executable, "-m", "pip", "install", pkg], check=True, capture_output=True)
                out["installed"].append(pkg)
            except Exception:
                out["failed"].append(pkg)
    try:
        import spacy
        try:
            spacy.load("it_core_news_sm")
        except Exception:
            subprocess.run([sys.executable, "-m", "spacy", "download", "it_core_news_sm"], check=True, capture_output=True)
            out["installed"].append("it_core_news_sm")
    except Exception:
        pass
    return out


def get_modello():
    try:
        with open("ollama_model.txt") as f:
            return f.read().strip()
    except Exception:
        return "mistral"


def ollama_disponibile():
    try:
        import requests
        requests.get("http://localhost:11434/api/tags", timeout=2)
        return True
    except Exception:
        return False


def spacy_disponibile():
    try:
        ensure_local_dependencies()
        import spacy
        spacy.load("it_core_news_sm")
        return True
    except Exception:
        return False


def estrai_aziende_da_testo(testo: str) -> list:
    """
    Usa spaCy per estrarre automaticamente nomi di organizzazioni
    da qualsiasi testo grezzo (HTML, descrizioni, articoli).
    Completamente offline, zero API, zero costi.
    """
    if not spacy_disponibile():
        logger.warning("[spaCy] Non disponibile")
        return []
    try:
        import spacy
        global _NLP
        if _NLP is None:
            _NLP = spacy.load("it_core_news_sm")
        nlp = _NLP
        doc = nlp(testo[:5000])
        aziende = list(set([
            ent.text.strip()
            for ent in doc.ents
            if ent.label_ in ("ORG", "PRODUCT")
            and len(ent.text.strip()) > 2
        ]))
        logger.info(f"[spaCy] Estratte {len(aziende)} organizzazioni dal testo")
        return aziende
    except Exception as e:
        logger.error(f"[spaCy] Errore: {e}")
        return []


def deduplica_intelligente(aziende: list, soglia: float = 0.85) -> list:
    """
    Usa sentence-transformers per trovare aziende duplicate
    anche se scritte in modo leggermente diverso.
    Es: "Alitalia SPA" e "Alitalia S.p.A." -> stesso risultato.
    Completamente offline.
    """
    if len(aziende) <= 1:
        return aziende
    try:
        ensure_local_dependencies()
        from sentence_transformers import SentenceTransformer
        from sklearn.metrics.pairwise import cosine_similarity

        global _SENTENCE_MODEL
        if _SENTENCE_MODEL is None:
            _SENTENCE_MODEL = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
        model = _SENTENCE_MODEL
        nomi = [a.get("name", a) if isinstance(a, dict) else a for a in aziende]
        embeddings = model.encode(nomi)
        similarity_matrix = cosine_similarity(embeddings)

        da_rimuovere = set()
        for i in range(len(nomi)):
            if i in da_rimuovere:
                continue
            for j in range(i + 1, len(nomi)):
                if similarity_matrix[i][j] > soglia:
                    da_rimuovere.add(j)
                    logger.info(f"[DEDUP] Rimosso duplicato: '{nomi[j]}' ≈ '{nomi[i]}'")

        uniche = [a for i, a in enumerate(aziende) if i not in da_rimuovere]
        logger.info(f"[DEDUP] {len(aziende)} -> {len(uniche)} aziende uniche")
        return uniche

    except Exception as e:
        logger.error(f"[DEDUP] Errore sentence-transformers: {e}")
        return aziende


def classifica_per_rilevanza(aziende: list, sector: str, country: str) -> list:
    """
    Usa TF-IDF per classificare e ordinare le aziende trovate
    in base alla loro rilevanza rispetto al settore cercato.
    """
    if not aziende:
        return aziende
    try:
        ensure_local_dependencies()
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity

        query = f"{sector} {country} azienda professionale"
        testi = [
            f"{a.get('name','')} {a.get('description','')} {a.get('sector','')}"
            if isinstance(a, dict) else a
            for a in aziende
        ]
        testi_con_query = [query] + testi

        vectorizer = TfidfVectorizer(
            stop_words=None,
            ngram_range=(1, 2),
            max_features=500
        )
        matrix = vectorizer.fit_transform(testi_con_query)
        scores = cosine_similarity(matrix[0:1], matrix[1:]).flatten()

        aziende_con_score = list(zip(aziende, scores))
        aziende_con_score.sort(key=lambda x: x[1], reverse=True)

        result = []
        for azienda, score in aziende_con_score:
            if isinstance(azienda, dict):
                azienda["relevance_score"] = round(float(score), 4)
            result.append(azienda)

        logger.info(f"[RANK] Classificate {len(result)} aziende per rilevanza")
        return result

    except Exception as e:
        logger.error(f"[RANK] Errore scikit-learn: {e}")
        return aziende


def analizza_azienda_con_ai(name: str, description: str, sector: str) -> dict:
    """
    Usa Ollama (AI locale gratuita) per analizzare e arricchire
    i dati di una singola azienda trovata.
    """
    if not ollama_disponibile():
        return {}
    try:
        import ollama
        modello = get_modello()
        prompt = f"""
Analizza questa azienda e restituisci SOLO JSON valido, nient'altro.

Nome: {name}
Descrizione: {description}
Settore ricercato: {sector}

JSON richiesto:
{{
  "settore_specifico": "sottosettore preciso",
  "tipo_azienda": "produttore / operatore / broker / fornitore / consulente",
  "dimensione_stimata": "startup / PMI / grande azienda",
  "rilevanza_settore": "alta / media / bassa",
  "parole_chiave": ["keyword1", "keyword2", "keyword3"]
}}
"""
        response = ollama.chat(
            model=modello,
            messages=[{"role": "user", "content": prompt}]
        )
        text = response["message"]["content"]
        start = text.find("{")
        end = text.rfind("}") + 1
        if start != -1 and end > start:
            return json.loads(text[start:end])
    except Exception as e:
        logger.error(f"[AI] Errore analisi '{name}': {e}")
    return {}


def analizza_risultati_ricerca(aziende: list, sector: str, country: str) -> list:
    """
    Pipeline completa:
    1. Estrai entità aggiuntive con spaCy
    2. Deduplica con sentence-transformers
    3. Classifica per rilevanza con scikit-learn
    4. Arricchisci top 10 con Ollama
    """
    logger.info(f"[ANALISI] Avvio pipeline analisi su {len(aziende)} aziende")
    dep = ensure_local_dependencies()
    if dep["installed"]:
        logger.info("[ANALISI] Dipendenze installate: %s", ", ".join(dep["installed"]))
    if dep["failed"]:
        logger.warning("[ANALISI] Dipendenze non installate: %s", ", ".join(dep["failed"]))

    aziende = deduplica_intelligente(aziende)
    aziende = classifica_per_rilevanza(aziende, sector, country)

    if ollama_disponibile():
        logger.info("[ANALISI] Arricchimento AI sui top risultati...")
        for i, azienda in enumerate(aziende[:10]):
            if isinstance(azienda, dict):
                extra = analizza_azienda_con_ai(
                    azienda.get("name", ""),
                    azienda.get("description", ""),
                    sector
                )
                if extra:
                    azienda.update(extra)
    else:
        logger.warning("[ANALISI] Ollama non disponibile, salto arricchimento AI")

    logger.info(f"[ANALISI] Pipeline completata: {len(aziende)} aziende processate")
    return aziende
