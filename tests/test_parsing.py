from datetime import date

import pytest

from feedvalidator.parsing import (
    as_text,
    modification_date,
    parse_iso_datetime,
    parse_nl_date,
    strip_html,
    validity_date,
)

SAMENGESTELD = "Laatst gewijzigd op: 05-08-2026 | Nog steeds geldig op: 14-09-2026"


def test_leest_beide_datums_uit_het_samengestelde_veld():
    assert modification_date(SAMENGESTELD) == date(2026, 8, 5)
    assert validity_date(SAMENGESTELD) == date(2026, 9, 14)


@pytest.mark.parametrize("waarde", ["", None, "Laatst gewijzigd op: binnenkort"])
def test_onleesbare_datum_geeft_none(waarde):
    assert modification_date(waarde) is None


def test_datum_met_een_cijfer_per_deel():
    assert parse_nl_date("5-8-2026") == date(2026, 8, 5)


def test_iso_timestamp_krijgt_altijd_een_tijdzone():
    moment = parse_iso_datetime("2026-08-05T09:23:35.512Z")
    assert moment is not None and moment.tzinfo is not None
    assert parse_iso_datetime("geen datum") is None


def test_strip_html_maakt_leesbare_tekst():
    assert strip_html("<p>Hoi <b>daar</b>&nbsp;!</p>") == "Hoi daar !"
    assert strip_html(None) == ""


def test_as_text_vlakt_lijsten_en_dicts_af():
    assert as_text(["Straat 1", "Madrid"]) == "Straat 1 Madrid"
    assert as_text({"a": "x", "b": ["y"]}) == "x y"
    assert as_text(None) == ""
