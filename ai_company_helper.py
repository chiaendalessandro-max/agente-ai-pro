import ollama
import json
import logging
import requests as http_requests

logger = logging.getLogger(__name__)

MODELLO = "llama3"


def is_ollama_available() -> bool:
    try:
        http_requests.get("http://localhost:11434/api/tags", timeout=2)
        return True
    except Exception:
        return False


def get_modello_disponibile() -> str:
    try:
        r = http_requests.get("http://localhost:11434/api/tags", timeout=2)
        modelli = r.json().get("models", [])
        nomi = [m["name"].split(":")[0] for m in modelli]
        for preferito in ["llama3", "mistral", "gemma2", "phi3"]:
            if preferito in nomi:
                logger.info(f"[AI] Modello selezionato: {preferito}")
                return preferito
        if nomi:
            return nomi[0]
    except Exception:
        pass
    return "llama3"


def ai_expand_search_queries(sector: str, country: str) -> list:
    if not is_ollama_available():
        logger.warning("[AI] Ollama non disponibile, salto generazione query AI")
        return []

    modello = get_modello_disponibile()
    prompt = f"""
Genera 10 query di ricerca Google per trovare aziende REALI nel settore "{sector}" in "{country}".

Regole OBBLIGATORIE:
- Query corte, 3-6 parole ciascuna
- Mix italiano e inglese
- Include parole come: elenco, lista, directory, aziende, companies, srl, spa
- Include termini settoriali precisi
- NON scrivere nomi di aziende
- NON aggiungere spiegazioni

Rispondi SOLO con array JSON di stringhe:
["query 1", "query 2", "query 3"]
"""
    try:
        response = ollama.chat(
            model=modello,
            messages=[{"role": "user", "content": prompt}]
        )
        text = response["message"]["content"]
        start = text.find("[")
        end = text.rfind("]") + 1
        if start != -1 and end > start:
            queries = json.loads(text[start:end])
            logger.info(f"[AI] Generate {len(queries)} query aggiuntive")
            return queries[:10]
    except Exception as e:
        logger.error(f"[AI] Errore generazione query: {e}")
    return []


def ai_validate_company(name: str, website: str, sector: str, country: str) -> bool:
    if not is_ollama_available():
        return True

    modello = get_modello_disponibile()
    prompt = f"""
Rispondi solo YES o NO.

"{name}" con sito "{website}" è una vera azienda nel settore "{sector}" in "{country}"?

Rispondi NO se:
- È un motore di ricerca, social media o Wikipedia
- Il nome è generico tipo "Global" o "International"
- Non ha un sito web reale
- È chiaramente un risultato sbagliato

Rispondi solo: YES oppure NO
"""
    try:
        response = ollama.chat(
            model=modello,
            messages=[{"role": "user", "content": prompt}]
        )
        answer = response["message"]["content"].strip().upper()
        valido = "YES" in answer
        logger.info(f"[AI] Validazione '{name}': {'OK' if valido else 'SCARTATA'}")
        return valido
    except Exception as e:
        logger.error(f"[AI] Errore validazione: {e}")
        return True


def ai_enrich_company(name: str, description: str, sector: str) -> dict:
    if not is_ollama_available():
        return {}

    modello = get_modello_disponibile()
    prompt = f"""
Azienda trovata:
Nome: {name}
Descrizione: {description}
Settore principale: {sector}

Restituisci SOLO questo JSON compilato, nient'altro:
{{
  "sector_specific": "sottosettore preciso",
  "company_type": "tipo azienda",
  "size_estimate": "startup oppure PMI oppure grande azienda"
}}
"""
    try:
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
        logger.error(f"[AI] Errore enrichment '{name}': {e}")
    return {}
