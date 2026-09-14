"""Vergelijking van de feed met de publiekssite nederlandwereldwijd.nl.

De site toont per reisadvies dezelfde regel als de feed ("Laatst gewijzigd
op ... | Nog steeds geldig op ..."). Door beide naast elkaar te leggen is
zichtbaar of een verschil bij een afnemer uit de feed komt of niet.
"""

from __future__ import annotations

import re
from typing import Any

import requests

from .config import Settings
from .parsing import parse_nl_date

_GEWIJZIGD_RE = re.compile(r"Laatst gewijzigd op:\s*(\d{1,2}-\d{1,2}-\d{4})", re.IGNORECASE)
_GELDIG_RE = re.compile(r"Nog steeds geldig op:\s*(\d{1,2}-\d{1,2}-\d{4})", re.IGNORECASE)
#: <meta name="DCTERMS.issued" content="2026-08-05T23:13"/> — de pushdatum
#: zoals de website hem publiceert, in Nederlandse tijd.
_ISSUED_RE = re.compile(
    r'name="DCTERMS\.issued"[^>]*content="([^"]+)"', re.IGNORECASE
)


def fetch_website_dates(
    session: requests.Session, url: str, settings: Settings
) -> dict[str, Any]:
    """Haal de getoonde wijzigings- en geldigheidsdatum van een publiekspagina."""
    result: dict[str, Any] = {"url": url}
    try:
        response = session.get(url, timeout=settings.timeout)
    except requests.RequestException as exc:
        result["error"] = str(exc)
        return result

    result["status"] = response.status_code
    if response.status_code != 200:
        result["error"] = f"HTTP {response.status_code}"
        return result

    html = response.text
    gewijzigd = _GEWIJZIGD_RE.search(html)
    geldig = _GELDIG_RE.search(html)
    if gewijzigd:
        parsed = parse_nl_date(gewijzigd.group(1))
        result["modification_date"] = parsed.isoformat() if parsed else None
    if geldig:
        parsed = parse_nl_date(geldig.group(1))
        result["validity_date"] = parsed.isoformat() if parsed else None
    gepusht = _ISSUED_RE.search(html)
    if gepusht:
        result["issued_raw"] = gepusht.group(1)
    if "modification_date" not in result:
        result["error"] = "Geen wijzigingsdatum op de pagina gevonden"
    return result
