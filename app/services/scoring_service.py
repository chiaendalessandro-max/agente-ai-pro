from typing import Any


PREMIUM_SECTORS = (
    "luxury",
    "finance",
    "bank",
    "wealth",
    "pharma",
    "biotech",
    "corporate",
    "private",
    "aviation",
)


def score_lead(payload: dict[str, Any]) -> tuple[int, str]:
    score = 0
    website = (payload.get("website") or "").strip()
    description = (payload.get("description") or "").lower()
    sector = (payload.get("sector") or "").lower()
    size_estimate = (payload.get("size_estimate") or "").lower()
    intl = int(payload.get("international_presence") or 0)
    has_email = bool(payload.get("has_corporate_email"))
    has_phone = bool(payload.get("has_phone"))

    if website.startswith("https://"):
        score += 12
    elif website:
        score += 6

    if len(description) > 140:
        score += 20
    elif len(description) > 70:
        score += 12

    if any(s in sector for s in PREMIUM_SECTORS):
        score += 20

    if "enterprise" in size_estimate or "500+" in size_estimate:
        score += 16
    elif "100+" in size_estimate:
        score += 10

    score += min(20, intl * 4)

    if has_email:
        score += 8
    if has_phone:
        score += 6

    score = max(0, min(100, score))
    if score >= 70:
        return score, "HIGH VALUE"
    if score >= 40:
        return score, "MEDIUM"
    return score, "LOW"
