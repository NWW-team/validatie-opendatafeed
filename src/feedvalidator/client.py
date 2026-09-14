"""HTTP-client voor de Nederland Wereldwijd opendatafeed (v2)."""

from __future__ import annotations

import logging
import time
from collections.abc import Iterator
from typing import Any
from urllib.parse import urljoin

import requests

from .config import MAX_ROWS_PER_PAGE, Settings

logger = logging.getLogger(__name__)

#: Statuscodes waarbij opnieuw proberen zin heeft.
RETRYABLE_STATUS = {429, 500, 502, 503, 504}


class FeedError(RuntimeError):
    """De feed gaf geen bruikbaar antwoord."""


class FeedClient:
    """Dunne wrapper om de feed: JSON forceren, pagineren, opnieuw proberen.

    Twee eigenaardigheden van de feed die hier afgevangen worden:

    * de standaard uitvoer is XML — ``output=json`` moet als queryparameter
      mee, want de ``Accept``-header wordt genegeerd;
    * ``rows`` wordt afgekapt op 200, dus lijsten moeten met ``offset``
      doorgebladerd worden.
    """

    def __init__(self, settings: Settings | None = None, session: requests.Session | None = None):
        self.settings = settings or Settings()
        self.session = session or requests.Session()
        self.session.headers.update({"User-Agent": self.settings.user_agent})

    # -- laag niveau ----------------------------------------------------

    def _url(self, path: str) -> str:
        return urljoin(self.settings.base_url.rstrip("/") + "/", path.lstrip("/"))

    def get(self, path: str, **params: Any) -> requests.Response:
        """Doe één GET met herhaalpogingen bij tijdelijke fouten."""
        url = self._url(path)
        last_error: Exception | None = None

        for attempt in range(1, self.settings.retries + 1):
            try:
                response = self.session.get(url, params=params, timeout=self.settings.timeout)
            except requests.RequestException as exc:  # netwerk-/TLS-fout
                last_error = exc
                logger.debug("poging %s voor %s mislukt: %s", attempt, url, exc)
            else:
                if response.status_code in RETRYABLE_STATUS:
                    last_error = FeedError(f"HTTP {response.status_code} voor {url}")
                    logger.debug(
                        "poging %s voor %s gaf HTTP %s", attempt, url, response.status_code
                    )
                else:
                    return response

            if attempt < self.settings.retries:
                time.sleep(min(2 ** (attempt - 1), 8))

        raise FeedError(f"{url} bleef falen na {self.settings.retries} pogingen: {last_error}")

    def get_json(self, path: str, **params: Any) -> Any:
        """Haal een endpoint op als JSON."""
        params.setdefault("output", "json")
        response = self.get(path, **params)
        if response.status_code != 200:
            raise FeedError(f"HTTP {response.status_code} voor {response.url}")
        try:
            return response.json()
        except ValueError as exc:
            raise FeedError(f"Geen geldige JSON van {response.url}: {exc}") from exc

    def paginate(self, path: str, **params: Any) -> Iterator[dict[str, Any]]:
        """Blader een lijst-endpoint door tot de laatste (deel)pagina."""
        offset = 0
        while True:
            page = self.get_json(path, rows=MAX_ROWS_PER_PAGE, offset=offset, **params)
            items = _as_list(page)
            yield from items
            if len(items) < MAX_ROWS_PER_PAGE:
                return
            offset += MAX_ROWS_PER_PAGE

    # -- endpoints ------------------------------------------------------

    def list_countries(self) -> list[dict[str, Any]]:
        """Alle landen uit de feed."""
        return list(self.paginate("infotypes/countries"))

    def list_traveladvice(self) -> list[dict[str, Any]]:
        """Index van alle reisadviezen (zonder inhoud, kaarten en datums)."""
        return list(self.paginate("infotypes/traveladvice"))

    def list_representations(self) -> list[dict[str, Any]]:
        """Index van alle Nederlandse vertegenwoordigingen."""
        return list(self.paginate("infotypes/nl-representation"))

    def list_emergency_info(self) -> list[dict[str, Any]]:
        """De 'hulp bij nood'-artikelen."""
        return list(self.paginate("infotypes/hulp-bij-nood"))

    def get_traveladvice(self, locationkey: str) -> dict[str, Any]:
        """Het volledige reisadvies van één land, inclusief kaarten en datums."""
        return _as_single(
            self.get_json(f"infotypes/countries/{locationkey}/traveladvice"),
            f"reisadvies {locationkey}",
        )

    def get_representations(self, locationkey: str) -> list[dict[str, Any]]:
        """De vertegenwoordigingen van één land (indexrecords)."""
        return _as_list(self.get_json(f"infotypes/countries/{locationkey}/nl-representation"))

    def get_representation(self, locationkey: str, representation_id: str) -> dict[str, Any]:
        """Eén vertegenwoordiging met adres-, telefoon- en e-mailgegevens."""
        return _as_single(
            self.get_json(
                f"infotypes/countries/{locationkey}/nl-representation/{representation_id}"
            ),
            f"vertegenwoordiging {locationkey}/{representation_id}",
        )

    def head_file(self, url: str) -> tuple[int, str, int]:
        """Vraag een bestand (kaart) op en geef status, mimetype en omvang terug.

        De feed antwoordt niet op HEAD, dus we halen het bestand streamend op
        en breken af zodra de headers binnen zijn.
        """
        response = self.session.get(url, timeout=self.settings.timeout, stream=True)
        try:
            size = int(response.headers.get("Content-Length") or 0)
            if not size:
                size = len(response.raw.read(1_048_576, decode_content=True) or b"")
            return response.status_code, response.headers.get("Content-Type", ""), size
        finally:
            response.close()


def _as_list(payload: Any) -> list[dict[str, Any]]:
    """Normaliseer een antwoord naar een lijst met records."""
    if payload is None:
        return []
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        # XML-achtige omhulsels die de feed soms teruggeeft.
        for key in ("documents", "document", "results"):
            if key in payload:
                return _as_list(payload[key])
        return [payload]
    return []


def _as_single(payload: Any, what: str) -> dict[str, Any]:
    """Normaliseer een detailantwoord (nu eens dict, dan weer lijst van één)."""
    items = _as_list(payload)
    if not items:
        raise FeedError(f"Leeg antwoord voor {what}")
    return items[0]
