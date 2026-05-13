"""Consultas y palabras clave en español (solo datos)."""

from __future__ import annotations

LANG_CODE = "es"

QUERY_BANK: dict[str, list[str]] = {
    "keywords": [
        "aviación privada",
        "fletamento aéreo",
        "jet ejecutivo",
        "vuelos charter",
        "aviación de negocios",
        "taxi aéreo",
    ],
    "synonyms": [
        "operadores de jet privado",
        "vuelos corporativos",
        "servicios de charter ejecutivo",
    ],
    "business_queries": [
        "empresas aviación españa",
        "operadores charter aéreo",
        "proveedores jet negocios",
    ],
    "premium_queries": [
        "operadores jet ejecutivo premium",
        "charter aéreo de alto nivel",
        "aviación corporativa exclusiva",
    ],
}
