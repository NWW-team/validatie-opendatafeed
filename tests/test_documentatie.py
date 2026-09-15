"""De documentatie moet het werkelijke aantal regels noemen.

De README liep een keer twee regels achter op de code. Dat is een klein
ongemak met een vervelend gevolg: wie het rapport naast de README legt, gaat
zoeken naar het verschil. Deze test laat de telling uit de regelcatalogus
komen in plaats van uit het geheugen van de schrijver.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from feedvalidator.rules import COUNTRY_RULES, FEED_RULES

WORTEL = Path(__file__).resolve().parents[1]

#: Documenten die een aantal regels noemen.
DOCUMENTEN = ["README.md", "docs/datastromen.md"]


@pytest.mark.parametrize("naam", DOCUMENTEN)
def test_document_noemt_het_werkelijke_aantal_regels(naam: str):
    tekst = (WORTEL / naam).read_text(encoding="utf-8")
    genoemd = {int(aantal) for aantal in re.findall(r"(\d+) regels", tekst)}
    assert genoemd == {len(FEED_RULES) + len(COUNTRY_RULES)}, (
        f"{naam} noemt {sorted(genoemd)} regels, de catalogus heeft er "
        f"{len(FEED_RULES) + len(COUNTRY_RULES)}"
    )


@pytest.mark.parametrize("naam", DOCUMENTEN)
def test_document_noemt_de_werkelijke_regelnummers(naam: str):
    tekst = (WORTEL / naam).read_text(encoding="utf-8")
    for regels, letter in ((FEED_RULES, "F"), (COUNTRY_RULES, "L")):
        nummers = sorted(regel.id for regel in regels)
        assert f"`{nummers[0]}`–`{nummers[-1]}`" in tekst, (
            f"{naam} noemt niet het bereik {nummers[0]}–{nummers[-1]} van de {letter}-regels"
        )
