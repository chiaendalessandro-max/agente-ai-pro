"""Palabras clave de sector y consultas de negocio (español). Claves alineadas con otras locales."""

from __future__ import annotations

LANG = "es"

KEYWORDS: dict[str, dict[str, list[str]]] = {
    "aviazione": {
        "sector_terms": [
            "aviación",
            "aviación general",
            "aviación de negocios",
            "jet privado",
            "taxi aéreo",
            "fletamento aéreo",
        ],
        "synonyms": ["operadores aéreos", "vuelos chárter", "jets corporativos"],
        "business_queries": [
            "empresas aviación España",
            "operadores jet privado",
            "servicios fletamento",
        ],
        "english_bridge": [
            "aviation",
            "private jet",
            "air charter",
            "business aviation",
        ],
    },
    "software": {
        "sector_terms": ["software", "saas", "aplicaciones", "nube"],
        "synonyms": ["desarrollo software", "soluciones IT"],
        "business_queries": ["empresas software España", "proveedores SaaS"],
        "english_bridge": ["software company", "SaaS", "enterprise software"],
    },
    "logistica": {
        "sector_terms": ["logística", "transporte", "carga", "supply chain"],
        "synonyms": ["mensajería", "almacén", "fulfillment"],
        "business_queries": ["empresas logística España", "operadores transporte"],
        "english_bridge": ["logistics", "freight", "supply chain"],
    },
}
