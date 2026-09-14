"""Gedeelde bouwstenen voor de tests: kleine, realistische feedrecords."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from feedvalidator.config import Settings
from feedvalidator.models import CountryRecord, FeedSnapshot


def nl_datum(dagen_geleden: int = 0) -> str:
    dag = datetime.now(UTC).date() - timedelta(days=dagen_geleden)
    return dag.strftime("%d-%m-%Y")


def iso_datum(dagen_geleden: int = 0) -> str:
    moment = datetime.now(UTC) - timedelta(days=dagen_geleden)
    return moment.isoformat().replace("+00:00", "Z")


def maak_reisadvies(**overrides: Any) -> dict[str, Any]:
    """Een reisadvies dat aan alle regels voldoet, tenzij je iets overschrijft."""
    advies = {
        "id": "ESP",
        "type": "reisadvies",
        "canonical": "https://www.nederlandwereldwijd.nl/reisadvies/spanje",
        "title": "Reisadvies Spanje | Ministerie van Buitenlandse Zaken",
        "introduction": "<h2>In het kort</h2><ul><li>Let op zakkenrollers in de grote steden "
        "en houd rekening met hitte in de zomermaanden.</li></ul>",
        "location": "Spanje",
        "locationkey": "spanje",
        "isocode": "ESP",
        "modificationdate": f"Laatst gewijzigd op: {nl_datum(10)} | "
        f"Nog steeds geldig op: {nl_datum(1)}",
        "content": [
            {
                "category": "Welke veiligheidsrisico's zijn er in Spanje?",
                "contentblocks": [
                    {"paragraphtitle": "Terrorisme", "paragraph": "<p>De kans is reëel.</p>"}
                ],
            }
        ],
        "files": [
            {
                "fileurl": "https://opendata.nederlandwereldwijd.nl/kaart.png",
                "mimetype": "image/png",
                "filesize": "202736",
                "filename": "Reisadvies_Spanje.png",
                "mapType": "legend",
            }
        ],
        "lastmodified": iso_datum(10),
        "issued": iso_datum(10),
        "available": iso_datum(2000),
        "language": "nl",
    }
    advies.update(overrides)
    return advies


def maak_vertegenwoordiging(**overrides: Any) -> dict[str, Any]:
    vertegenwoordiging = {
        "id": "ambassade-madrid",
        "title": "Nederlandse ambassade in Madrid, Spanje",
        "address": ["Pº de la Castellana 259-D", "28046 Madrid", "Spanje"],
        "telephonenumbers": ["+34 91 353 75 00"],
        "emailaddress": "mad@minbuza.nl",
        "emergencynumber": "+31 247 247 247",
        "embassy": True,
    }
    vertegenwoordiging.update(overrides)
    return vertegenwoordiging


def maak_record(**overrides: Any) -> CountryRecord:
    velden: dict[str, Any] = {
        "locationkey": "spanje",
        "location": "Spanje",
        "isocode": "ESP",
        "traveladvice": maak_reisadvies(),
        "representations": [maak_vertegenwoordiging()],
    }
    velden.update(overrides)
    # Het landrecord uit /infotypes/countries hoort bij het land te passen,
    # anders toetsen de feedregels iets anders dan de landregels.
    velden.setdefault(
        "country",
        {
            "locationkey": velden["locationkey"],
            "location": velden["location"],
            "isocode": velden["isocode"],
        },
    )
    return CountryRecord(**velden)


def maak_snapshot(records: list[CountryRecord] | None = None, **overrides: Any) -> FeedSnapshot:
    records = records if records is not None else [maak_record()]
    velden: dict[str, Any] = {
        "fetched_at": datetime.now(UTC),
        "base_url": "https://opendata.nederlandwereldwijd.nl/v2/sources/nederlandwereldwijd",
        "countries": [r.country for r in records],
        "traveladvice_index": [
            {"locationkey": r.locationkey, "location": r.location, "isocode": r.isocode}
            for r in records
        ],
        "representation_index": [],
        "emergency_info": [{"id": "bestolen-buitenland"}],
        "records": records,
    }
    velden.update(overrides)
    return FeedSnapshot(**velden)


@pytest.fixture
def settings() -> Settings:
    return Settings(workers=1, retries=1)
