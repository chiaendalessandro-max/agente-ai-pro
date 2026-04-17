from datetime import datetime, timedelta, timezone


def next_followup_iso(days: int = 2) -> str:
    return (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()
