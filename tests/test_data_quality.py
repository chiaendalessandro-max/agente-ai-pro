"""Test puri sulla normalizzazione dati (nessun DB / nessuna rete)."""
from __future__ import annotations

from app.services.data_quality import (
    dedupe_leads_by_domain,
    is_blocked_or_junk_domain,
    normalize_domain,
    normalize_lead_dict,
    normalize_website_url,
)


def test_normalize_domain_strips_www_and_path() -> None:
    assert normalize_domain("https://WWW.Example.COM/foo") == "example.com"


def test_normalize_website_adds_scheme() -> None:
    assert normalize_website_url("example.com").startswith("https://")


def test_blocked_social_domains() -> None:
    assert is_blocked_or_junk_domain("linkedin.com") is True
    assert is_blocked_or_junk_domain("acme-corp.io") is False


def test_normalize_lead_dict_bounds() -> None:
    raw = {
        "name": "X" * 300,
        "domain": "acme.io",
        "website": "https://acme.io",
        "score": 999,
        "classification": "HIGH VALUE",
        "international_presence": 99,
    }
    out = normalize_lead_dict(raw, "seed query")
    assert out["score"] == 100
    assert out["international_presence"] == 20
    assert len(out["name"]) <= 200


def test_dedupe_leads_by_domain() -> None:
    leads = [
        {"domain": "a.com", "website": "https://a.com", "score": 1},
        {"domain": "a.com", "website": "https://a.com/", "score": 2},
        {"domain": "b.com", "website": "https://b.com", "score": 3},
    ]
    assert len(dedupe_leads_by_domain(leads)) == 2
