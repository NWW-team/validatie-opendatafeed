"""Elke regel krijgt een geval dat slaagt en een geval dat faalt."""

from __future__ import annotations

import pytest

from conftest import (
    iso_datum,
    maak_record,
    maak_reisadvies,
    maak_snapshot,
    maak_vertegenwoordiging,
    nl_datum,
)
from feedvalidator.config import Settings, Thresholds
from feedvalidator.models import Severity
from feedvalidator.parsing import as_text, modification_date
from feedvalidator.rules import COUNTRY_RULES, FEED_RULES, rule_by_id
from feedvalidator.validate import run_rules


def draai(rule_id: str, record, settings: Settings):
    return list(rule_by_id(rule_id).check(record, settings))


def test_alle_regels_hebben_een_uniek_id_en_uitleg():
    ids = [r.id for r in FEED_RULES + COUNTRY_RULES]
    assert len(ids) == len(set(ids))
    for regel in FEED_RULES + COUNTRY_RULES:
        assert regel.title and regel.description
        assert regel.severity in set(Severity)


def test_een_volledig_land_levert_geen_enkele_bevinding():
    ruim = Settings(thresholds=Thresholds(min_aantal_reisadviezen=1))
    rapport = run_rules(maak_snapshot(), ruim)
    assert rapport.findings == []
    assert rapport.healthy


# -- feedregels ------------------------------------------------------------


def test_f01_meldt_een_endpoint_dat_niet_antwoordt(settings):
    snapshot = maak_snapshot(fetch_errors={"countries": "HTTP 503"})
    bevindingen = draai("F01", snapshot, settings)
    assert len(bevindingen) == 1
    assert "countries" in bevindingen[0].message


def test_f02_slaat_alarm_bij_te_weinig_reisadviezen(settings):
    krap = Settings(thresholds=Thresholds(min_aantal_reisadviezen=5))
    bevindingen = draai("F02", maak_snapshot(), krap)
    assert len(bevindingen) == 1
    assert "ondergrens" in bevindingen[0].message


def test_f03_vindt_een_land_zonder_reisadvies(settings):
    snapshot = maak_snapshot(traveladvice_index=[])
    bevindingen = draai("F03", snapshot, settings)
    assert len(bevindingen) == 1
    assert "geen reisadvies" in bevindingen[0].message


def test_f04_vindt_een_reisadvies_zonder_land(settings):
    snapshot = maak_snapshot(countries=[])
    bevindingen = draai("F04", snapshot, settings)
    assert len(bevindingen) == 1


def test_f05_vindt_dubbele_isocodes(settings):
    land = {"locationkey": "spanje", "location": "Spanje", "isocode": "ESP"}
    snapshot = maak_snapshot(countries=[land, dict(land)])
    boodschappen = [b.message for b in draai("F05", snapshot, settings)]
    assert any("ISO-code 'ESP' komt 2 keer voor" in m for m in boodschappen)
    assert any("landsleutel 'spanje' komt 2 keer voor" in m for m in boodschappen)


def test_f06_meldt_lege_hulp_bij_nood(settings):
    assert draai("F06", maak_snapshot(emergency_info=[]), settings)


def test_f07_meldt_een_contactveld_dat_feedbreed_leeg_is(settings):
    leeg = maak_vertegenwoordiging(
        telephonenumbers=[], phonenumbers=[], emailaddress="", emergencynumber=""
    )
    snapshot = maak_snapshot([maak_record(representations=[leeg])])
    labels = {b.detail["veld"] for b in draai("F07", snapshot, settings)}
    assert labels == {"telefoonnummer", "e-mailadres", "noodnummer"}


def test_f07_zwijgt_zodra_een_veld_ergens_gevuld_is(settings):
    snapshot = maak_snapshot([maak_record()])
    labels = {b.detail["veld"] for b in draai("F07", snapshot, settings)}
    assert "telefoonnummer" not in labels and "e-mailadres" not in labels


# -- landregels ------------------------------------------------------------


def test_l01_meldt_een_onbereikbaar_reisadvies(settings):
    record = maak_record(traveladvice=None, fetch_errors={"traveladvice": "HTTP 500"})
    assert "HTTP 500" in draai("L01", record, settings)[0].message


@pytest.mark.parametrize(
    "code, verwacht",
    [("ESP", 0), ("XKX", 0), ("", 1), ("ES", 1), ("esp", 1), ("ZZZ", 1)],
)
def test_l02_toetst_de_isocode(settings, code, verwacht):
    record = maak_record(isocode=code or None)
    assert len(draai("L02", record, settings)) == verwacht


def test_l02_accepteert_een_code_die_het_team_toestaat():
    toegestaan = Settings(extra_isocodes=frozenset({"BQ-BO"}))
    assert draai("L02", maak_record(isocode="BQ-BO"), toegestaan) == []
    assert len(draai("L02", maak_record(isocode="BQ-BO"), Settings())) == 1


def test_l03_ziet_verschil_tussen_land_en_reisadvies(settings):
    record = maak_record(traveladvice=maak_reisadvies(isocode="PRT"))
    assert len(draai("L03", record, settings)) == 1


def test_l04_meldt_een_lege_titel(settings):
    record = maak_record(traveladvice=maak_reisadvies(title=""))
    assert len(draai("L04", record, settings)) == 1


def test_l05_meldt_een_ontbrekende_of_te_korte_introductie(settings):
    zonder = maak_record(traveladvice=maak_reisadvies(introduction=""))
    assert len(draai("L05", zonder, settings)) == 1
    kort = maak_record(traveladvice=maak_reisadvies(introduction="<p>Kort.</p>"))
    assert "korter dan de ondergrens" in draai("L05", kort, settings)[0].message


def test_l06_meldt_een_reisadvies_zonder_inhoud(settings):
    leeg = maak_record(traveladvice=maak_reisadvies(content=[]))
    assert len(draai("L06", leeg, settings)) == 1
    zonder_blokken = maak_record(
        traveladvice=maak_reisadvies(content=[{"category": "Veiligheid", "contentblocks": []}])
    )
    assert "zonder enig tekstblok" in draai("L06", zonder_blokken, settings)[0].message


def test_l07_meldt_een_leeg_tekstblok(settings):
    record = maak_record(
        traveladvice=maak_reisadvies(
            content=[
                {
                    "category": "Veiligheid",
                    "contentblocks": [{"paragraphtitle": "Terrorisme", "paragraph": "<p> </p>"}],
                }
            ]
        )
    )
    assert "is leeg" in draai("L07", record, settings)[0].message


def test_l08_meldt_een_reisadvies_zonder_kaart(settings):
    record = maak_record(traveladvice=maak_reisadvies(files=[]))
    assert len(draai("L08", record, settings)) == 1


def test_l08_telt_een_niet_kaart_bijlage_niet_mee(settings):
    bijlage = {
        "fileurl": "https://feed/doc.pdf",
        "mimetype": "application/pdf",
        "filename": "x.pdf",
    }
    record = maak_record(traveladvice=maak_reisadvies(files=[bijlage]))
    assert len(draai("L08", record, settings)) == 1


def test_l09_meldt_ontbrekende_kaartvelden(settings):
    kaart = {"mapType": "legend", "filename": "kaart.png"}
    record = maak_record(traveladvice=maak_reisadvies(files=[kaart]))
    bevinding = draai("L09", record, settings)[0]
    assert "fileurl" in bevinding.message and "mimetype" in bevinding.message


def test_l10_draait_alleen_met_check_files():
    aan = Settings(check_files=True)
    record = maak_record(
        map_checks=[{"url": "https://feed/kaart.png", "ok": False, "reden": "HTTP 404"}]
    )
    assert "HTTP 404" in draai("L10", record, aan)[0].message
    assert draai("L10", maak_record(map_checks=[{"ok": True}]), aan) == []


def test_l11_meldt_een_onleesbare_wijzigingsdatum(settings):
    zonder = maak_record(traveladvice=maak_reisadvies(modificationdate=""))
    assert "geen wijzigingsdatum" in draai("L11", zonder, settings)[0].message
    rommel = maak_record(traveladvice=maak_reisadvies(modificationdate="onbekend"))
    assert "niet te lezen" in draai("L11", rommel, settings)[0].message


def test_l12_ziet_verschil_tussen_getoonde_en_technische_datum(settings):
    record = maak_record(
        traveladvice=maak_reisadvies(
            modificationdate=f"Laatst gewijzigd op: {nl_datum(30)} | "
            f"Nog steeds geldig op: {nl_datum(1)}",
            lastmodified=iso_datum(2),
        )
    )
    assert len(draai("L12", record, settings)) == 1


def test_l13_meldt_een_datum_in_de_toekomst(settings):
    record = maak_record(traveladvice=maak_reisadvies(lastmodified=iso_datum(-5)))
    assert "in de toekomst" in draai("L13", record, settings)[0].message


def test_l14_meldt_een_verlopen_geldigheidsdatum(settings):
    record = maak_record(
        traveladvice=maak_reisadvies(
            modificationdate=f"Laatst gewijzigd op: {nl_datum(400)} | "
            f"Nog steeds geldig op: {nl_datum(365)}"
        )
    )
    assert "geldig verklaard" in draai("L14", record, settings)[0].message


def test_l15_meldt_een_lang_ongewijzigd_advies(settings):
    record = maak_record(traveladvice=maak_reisadvies(lastmodified=iso_datum(500)))
    assert "niet gewijzigd" in draai("L15", record, settings)[0].message


def test_l16_meldt_een_verkeerde_canonical(settings):
    zonder = maak_record(traveladvice=maak_reisadvies(canonical=""))
    assert len(draai("L16", zonder, settings)) == 1
    fout = maak_record(traveladvice=maak_reisadvies(canonical="http://voorbeeld.nl/spanje"))
    assert len(draai("L16", fout, settings)) == 1


def test_l17_meldt_een_land_zonder_vertegenwoordiging(settings):
    assert len(draai("L17", maak_record(representations=[]), settings)) == 1
    stuk = maak_record(representations=[], fetch_errors={"nl-representation": "HTTP 500"})
    assert "niet op te halen" in draai("L17", stuk, settings)[0].message


def test_l18_meldt_een_post_waarvan_het_adres_nergens_staat(settings):
    kaal = maak_vertegenwoordiging(address=[""])
    bevinding = draai("L18", maak_record(representations=[kaal]), settings)[0]
    assert "nergens een adres" in bevinding.message


def test_l18_laat_een_ambassade_met_adres_met_rust(settings):
    zonder_mail = maak_vertegenwoordiging(emailaddress="")
    assert draai("L18", maak_record(representations=[zonder_mail]), settings) == []


def test_l18_accepteert_een_verwijzing_naar_een_post_in_een_ander_land(settings):
    # Amerikaans-Samoa wordt bediend door de ambassade in Wellington: hetzelfde
    # id, geen eigen adresregels, adres staat bij Nieuw-Zeeland.
    verwijzing = maak_vertegenwoordiging(id="ambassade-wellington", address=[""])
    bediend = maak_record(
        locationkey="amerikaans-samoa",
        location="Amerikaans-Samoa",
        isocode="ASM",
        representations=[verwijzing],
        address_elsewhere={"ambassade-wellington": "Nieuw-Zeeland"},
    )

    assert draai("L18", bediend, settings) == []


def test_l19_vergelijkt_met_de_website():
    aan = Settings(check_website=True)
    record = maak_record(website={"url": "https://site/spanje", "modification_date": "2000-01-01"})
    assert "de website" in draai("L19", record, aan)[0].message

    stuk = maak_record(website={"url": "https://site/spanje", "error": "HTTP 404"})
    assert "niet op te halen" in draai("L19", stuk, aan)[0].message


def test_f08_meldt_een_uitsluiting_die_niet_meer_nodig_is():
    opgeruimd = Settings(excluded_countries=frozenset({"vaticaanstad"}))
    snapshot = maak_snapshot([maak_record()])  # alleen Spanje staat nog in de feed

    bevinding = draai("F08", snapshot, opgeruimd)[0]

    assert "kan weg" in bevinding.message
    assert bevinding.detail["landsleutel"] == "vaticaanstad"


def test_f08_zwijgt_zolang_het_land_nog_in_de_feed_staat():
    nog_aanwezig = Settings(excluded_countries=frozenset({"vaticaanstad"}))
    snapshot = maak_snapshot(
        [maak_record(), maak_record(locationkey="vaticaanstad", location="Vaticaanstad")]
    )

    assert draai("F08", snapshot, nog_aanwezig) == []


def test_f08_zwijgt_zonder_uitsluitingen(settings):
    assert draai("F08", maak_snapshot(), settings) == []


# -- pushdatum (het veld issued) -------------------------------------------


def test_l20_meldt_een_ontbrekende_of_onleesbare_pushdatum(settings):
    zonder = maak_record(traveladvice=maak_reisadvies(issued=""))
    assert "geen pushdatum" in draai("L20", zonder, settings)[0].message
    rommel = maak_record(traveladvice=maak_reisadvies(issued="vorige week"))
    assert "geen geldige timestamp" in draai("L20", rommel, settings)[0].message


def test_l21_meldt_een_pushdatum_in_de_toekomst(settings):
    vooruit = maak_record(traveladvice=maak_reisadvies(issued=iso_datum(-3)))
    assert "in de toekomst" in draai("L21", vooruit, settings)[0].message
    assert draai("L21", maak_record(), settings) == []


def test_l22_meldt_een_push_van_voor_de_eerste_publicatie(settings):
    omgedraaid = maak_record(
        traveladvice=maak_reisadvies(issued=iso_datum(500), available=iso_datum(100))
    )
    assert "vóór de eerste publicatie" in draai("L22", omgedraaid, settings)[0].message
    assert draai("L22", maak_record(), settings) == []


def test_l23_meldt_een_recente_wijziging_die_niet_gepusht_is(settings):
    # Vijf dagen geleden gewijzigd, maar de laatste push was een jaar eerder.
    record = maak_record(
        traveladvice=maak_reisadvies(
            modificationdate=f"Laatst gewijzigd op: {nl_datum(5)} | "
            f"Nog steeds geldig op: {nl_datum(1)}",
            issued=iso_datum(370),
        )
    )
    bevinding = draai("L23", record, settings)[0]
    assert "de laatste push was" in bevinding.message
    assert bevinding.detail["venster_dagen"] == 30


def test_l23_zwijgt_over_een_oude_wijziging_buiten_het_venster(settings):
    # Buiten het venster: dit is de normale toestand van een stabiel advies.
    record = maak_record(
        traveladvice=maak_reisadvies(
            modificationdate=f"Laatst gewijzigd op: {nl_datum(200)} | "
            f"Nog steeds geldig op: {nl_datum(1)}",
            issued=iso_datum(370),
        )
    )
    assert draai("L23", record, settings) == []


def test_l23_zwijgt_als_de_push_na_de_wijziging_kwam(settings):
    record = maak_record(
        traveladvice=maak_reisadvies(
            modificationdate=f"Laatst gewijzigd op: {nl_datum(5)} | "
            f"Nog steeds geldig op: {nl_datum(1)}",
            issued=iso_datum(4),
        )
    )
    assert draai("L23", record, settings) == []


def test_f09_meldt_een_bulkpush(settings):
    # Eén en dezelfde timestamp: zo ziet een bulkactie eruit in de feed.
    bulkmoment = "2023-08-07T20:26:00.000Z"
    bulk = [maak_record(traveladvice=maak_reisadvies(issued=bulkmoment)) for _ in range(9)]
    verspreid = [maak_record(traveladvice=maak_reisadvies(issued=iso_datum(n))) for n in range(5)]

    bevinding = draai("F09", maak_snapshot(bulk + verspreid), settings)[0]

    assert "bulkactie" in bevinding.message
    assert bevinding.detail["aantal"] == 9


def test_f09_zwijgt_bij_verspreide_pushdatums(settings):
    verspreid = [maak_record(traveladvice=maak_reisadvies(issued=iso_datum(n))) for n in range(14)]
    assert draai("F09", maak_snapshot(verspreid), settings) == []


def test_l19_vergelijkt_ook_de_pushdatum():
    aan = Settings(check_website=True)
    record = maak_record(
        traveladvice=maak_reisadvies(issued="2026-08-05T21:13:00.000Z"),
        website={
            "url": "https://site/spanje",
            "modification_date": modification_date(
                as_text(maak_reisadvies()["modificationdate"])
            ).isoformat(),
            "issued_raw": "2026-07-01T10:00",
        },
    )

    boodschappen = [b.message for b in draai("L19", record, aan)]

    assert any("pushdatum" in m for m in boodschappen)


def test_f10_meldt_dat_de_ronde_is_afgeknepen(settings):
    getroffen = maak_record(rate_limited=True, traveladvice=None)
    snapshot = maak_snapshot([maak_record(), getroffen], rate_limited=12)

    bevinding = draai("F10", snapshot, settings)[0]

    assert "afgeknepen" in bevinding.message
    assert bevinding.detail == {"verzoeken": 12, "landen": 1}


def test_f10_zwijgt_bij_een_ronde_zonder_429(settings):
    assert draai("F10", maak_snapshot(), settings) == []


def test_l01_verwijt_de_feed_niets_bij_een_afgeknepen_verzoek(settings):
    afgeknepen = maak_record(
        rate_limited=True,
        traveladvice=None,
        fetch_errors={"traveladvice": "werd afgeknepen (HTTP 429)"},
    )
    assert draai("L01", afgeknepen, settings) == []

    echt_stuk = maak_record(traveladvice=None, fetch_errors={"traveladvice": "HTTP 500"})
    assert len(draai("L01", echt_stuk, settings)) == 1


def test_l17_verwijt_de_feed_niets_bij_een_afgeknepen_verzoek(settings):
    afgeknepen = maak_record(
        rate_limited=True,
        representations=[],
        fetch_errors={"nl-representation": "werd afgeknepen (HTTP 429)"},
    )
    assert draai("L17", afgeknepen, settings) == []


def test_f11_benoemt_de_landen_die_vanuit_een_andere_post_worden_bediend(settings):
    bediend = maak_record(
        locationkey="amerikaans-samoa", location="Amerikaans-Samoa", isocode="ASM",
        address_elsewhere={"ambassade-wellington": "Nieuw-Zeeland"},
    )
    snapshot = maak_snapshot([maak_record(), bediend])

    bevinding = draai("F11", snapshot, settings)[0]

    assert "bediend door een post in een ander land" in bevinding.message
    assert bevinding.detail == {"aantal_landen": 1, "aantal_posten": 1}


def test_f11_zwijgt_als_elk_land_een_eigen_post_heeft(settings):
    assert draai("F11", maak_snapshot(), settings) == []


def test_l18_legt_uit_waarom_er_geen_adres_is(settings):
    kaal = maak_vertegenwoordiging(address=[""])
    bericht = draai("L18", maak_record(representations=[kaal]), settings)[0].message
    assert "verwijst ook niet naar een post in een ander land" in bericht
