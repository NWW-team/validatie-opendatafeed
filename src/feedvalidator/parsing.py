"""Hulpfuncties om feedwaarden te lezen: datums, HTML-tekst, lijstvelden."""

from __future__ import annotations

import html
import re
from datetime import UTC, date, datetime
from typing import Any

#: "Laatst gewijzigd op: 05-08-2026 | Nog steeds geldig op: 14-09-2026"
_GEWIJZIGD_RE = re.compile(r"laatst gewijzigd op:\s*(\d{1,2}-\d{1,2}-\d{4})", re.IGNORECASE)
_GELDIG_RE = re.compile(r"nog steeds geldig op:\s*(\d{1,2}-\d{1,2}-\d{4})", re.IGNORECASE)
_TAG_RE = re.compile(r"<[^>]+>")


def parse_nl_date(value: str | None) -> date | None:
    """Lees een Nederlandse datum (dd-mm-jjjj) uit een tekst."""
    if not value:
        return None
    try:
        return datetime.strptime(value.strip(), "%d-%m-%Y").date()
    except ValueError:
        return None


def parse_iso_datetime(value: str | None) -> datetime | None:
    """Lees een ISO 8601-timestamp; geeft altijd een tijdzonebewuste waarde."""
    if not value:
        return None
    text = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed


def modification_date(modificationdate: str | None) -> date | None:
    """De 'Laatst gewijzigd op'-datum uit het samengestelde tekstveld."""
    if not modificationdate:
        return None
    match = _GEWIJZIGD_RE.search(modificationdate)
    return parse_nl_date(match.group(1)) if match else None


def validity_date(modificationdate: str | None) -> date | None:
    """De 'Nog steeds geldig op'-datum uit het samengestelde tekstveld."""
    if not modificationdate:
        return None
    match = _GELDIG_RE.search(modificationdate)
    return parse_nl_date(match.group(1)) if match else None


def strip_html(value: str | None) -> str:
    """Maak platte tekst van een HTML-fragment, zodat lengtes iets zeggen."""
    if not value:
        return ""
    text = _TAG_RE.sub(" ", value)
    return " ".join(html.unescape(text).split())


def as_text(value: Any) -> str:
    """Lees een veld dat een string, een lijst of niets kan zijn, als tekst."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (list, tuple)):
        return " ".join(as_text(item) for item in value).strip()
    if isinstance(value, dict):
        return " ".join(as_text(item) for item in value.values()).strip()
    return str(value).strip()


def first_nonempty(record: dict[str, Any], *keys: str) -> str:
    """De eerste van ``keys`` die in ``record`` een gevulde waarde heeft."""
    for key in keys:
        text = as_text(record.get(key))
        if text:
            return text
    return ""


def days_between(earlier: date, later: date) -> int:
    """Aantal dagen tussen twee datums (negatief als ``earlier`` later ligt)."""
    return (later - earlier).days
