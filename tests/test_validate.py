"""Het ophalen, de parallelle verrijking en de exitcodes."""

from __future__ import annotations

from conftest import maak_record, maak_reisadvies, maak_snapshot, maak_vertegenwoordiging
from feedvalidator.client import FeedError
from feedvalidator.config import Settings, Thresholds
from feedvalidator.models import Severity
from feedvalidator.snapshot import load_snapshot, save_snapshot
from feedvalidator.validate import (
    _probe_maps,
    exit_code,
    fetch_snapshot,
    resolve_addresses,
    run_rules,
)


class NepClient:
    """Een client die uit geheugen antwoordt, zonder netwerk."""

    def __init__(self, landen, adviezen=None, vertegenwoordigingen=None, stuk=()):
        self.landen = landen
        self.adviezen = adviezen or {}
        self.vertegenwoordigingen = vertegenwoordigingen or {}
        self.stuk = set(stuk)
        self.session = None
        self.rate_limited = 0
        self.opgehaald: list[str] = []

    def list_countries(self):
        return self.landen

    def list_traveladvice(self):
        return [{"locationkey": land.get("locationkey", "")} for land in self.landen]

    def list_representations(self):
        return []

    def list_emergency_info(self):
        return [{"id": "bestolen-buitenland"}]

    def get_traveladvice(self, locationkey):
        self.opgehaald.append(locationkey)
        if locationkey in self.stuk:
            raise FeedError("HTTP 500")
        return self.adviezen.get(locationkey, maak_reisadvies(locationkey=locationkey))

    def get_representations(self, locationkey):
        return [{"id": "ambassade"}] if locationkey in self.vertegenwoordigingen else []

    def get_representation(self, locationkey, representation_id):
        return self.vertegenwoordigingen[locationkey]


def landen(*sleutels):
    return [
        {"locationkey": s, "location": s.capitalize(), "isocode": s[:3].upper()} for s in sleutels
    ]


def test_haalt_alle_landen_op_en_verrijkt_ze():
    client = NepClient(
        landen("spanje", "portugal"), vertegenwoordigingen={"spanje": maak_vertegenwoordiging()}
    )
    snapshot = fetch_snapshot(client, Settings(workers=2))

    assert sorted(client.opgehaald) == ["portugal", "spanje"]
    assert len(snapshot.records) == 2
    assert snapshot.records[0].traveladvice is not None
    assert snapshot.records[0].representations


def test_limit_beperkt_het_aantal_landen():
    client = NepClient(landen("spanje", "portugal", "frankrijk"))
    snapshot = fetch_snapshot(client, Settings(limit=1, workers=1))
    assert [r.locationkey for r in snapshot.records] == ["spanje"]


def test_een_kapot_detail_endpoint_blokkeert_de_rest_niet():
    client = NepClient(landen("spanje", "portugal"), stuk={"portugal"})
    snapshot = fetch_snapshot(client, Settings(workers=1))

    kapot = [r for r in snapshot.records if r.locationkey == "portugal"][0]
    heel = [r for r in snapshot.records if r.locationkey == "spanje"][0]
    assert "HTTP 500" in kapot.fetch_errors["traveladvice"]
    assert heel.traveladvice is not None


def test_land_zonder_locationkey_wordt_gemeld_en_niet_opgehaald():
    client = NepClient([{"location": "Nergens", "isocode": "NER"}])
    snapshot = fetch_snapshot(client, Settings(workers=1))
    assert client.opgehaald == []
    assert "locationkey" in snapshot.records[0].fetch_errors["traveladvice"]


class NepBestandClient:
    def __init__(self, antwoord):
        self.antwoord = antwoord

    def head_file(self, url):
        if isinstance(self.antwoord, Exception):
            raise self.antwoord
        return self.antwoord


def test_kaartcontrole_keurt_een_afbeelding_goed():
    probes = _probe_maps(NepBestandClient((200, "image/png", 1234)), maak_reisadvies())
    assert probes[0]["ok"] is True


def test_kaartcontrole_ziet_een_dode_link_en_een_verkeerd_type():
    def reden(antwoord):
        return _probe_maps(NepBestandClient(antwoord), maak_reisadvies())[0]["reden"]

    assert reden((404, "text/html", 0)) == "HTTP 404"
    assert "mimetype" in reden((200, "text/html", 10))
    assert "leeg" in reden((200, "image/png", 0))


def test_kaart_zonder_url_wordt_gemeld():
    advies = maak_reisadvies(files=[{"mapType": "legend", "filename": "kaart.png"}])
    probes = _probe_maps(NepBestandClient((200, "image/png", 1)), advies)
    assert probes[0]["reden"] == "geen fileurl"


def test_rapport_telt_regels_en_bevindingen():
    ruim = Settings(thresholds=Thresholds(min_aantal_reisadviezen=1))
    rapport = run_rules(maak_snapshot([maak_record(), maak_record(isocode="ZZZ")]), ruim)

    iso_regel = [r for r in rapport.results if r.rule_id == "L02"][0]
    assert iso_regel.checked == 2
    assert iso_regel.failed == 1
    assert iso_regel.passed == 1
    assert rapport.countries_checked == 2


def test_exitcode_volgt_de_gekozen_drempel():
    ruim = Settings(thresholds=Thresholds(min_aantal_reisadviezen=1))
    schoon = run_rules(maak_snapshot(), ruim)
    fout = run_rules(maak_snapshot([maak_record(isocode="ZZZ")]), ruim)
    waarschuwing = run_rules(maak_snapshot([maak_record(representations=[])]), ruim)

    assert exit_code(schoon, "error") == 0
    assert exit_code(fout, "error") == 1
    assert exit_code(waarschuwing, "error") == 0
    assert exit_code(waarschuwing, "warning") == 1
    assert exit_code(fout, "never") == 0


def test_onbereikbaar_endpoint_maakt_het_rapport_ongezond():
    ruim = Settings(thresholds=Thresholds(min_aantal_reisadviezen=1))
    rapport = run_rules(maak_snapshot(fetch_errors={"countries": "HTTP 503"}), ruim)
    assert not rapport.healthy
    assert rapport.count(Severity.ERROR) >= 1
    assert exit_code(rapport, "error") == 1


def test_snapshot_overleeft_opslaan_en_terugladen(tmp_path):
    origineel = maak_snapshot()
    pad = save_snapshot(origineel, tmp_path / "snapshot.json")
    terug = load_snapshot(pad)

    assert terug.base_url == origineel.base_url
    assert [r.locationkey for r in terug.records] == [r.locationkey for r in origineel.records]
    assert terug.records[0].traveladvice == origineel.records[0].traveladvice

    ruim = Settings(thresholds=Thresholds(min_aantal_reisadviezen=1))
    assert run_rules(terug, ruim).findings == []


def test_uitgesloten_land_wordt_wel_opgehaald_maar_niet_getoetst():
    # Ophalen blijft nodig: een post in het uitgesloten land kan het adres
    # dragen waar een ander land naar verwijst.
    client = NepClient(landen("spanje", "vaticaanstad"))
    settings = Settings(
        workers=1,
        excluded_countries=frozenset({"vaticaanstad"}),
        thresholds=Thresholds(min_aantal_reisadviezen=1),
    )

    snapshot = fetch_snapshot(client, settings)

    assert sorted(client.opgehaald) == ["spanje", "vaticaanstad"]
    assert len(snapshot.records) == 2

    rapport = run_rules(snapshot, settings)
    assert rapport.countries_checked == 1
    assert rapport.excluded == ["Vaticaanstad (vaticaanstad)"]


def test_adres_uit_een_uitgesloten_land_telt_nog_steeds_mee():
    # Italië verwijst naar de ambassade bij de Heilige Stoel; dat Vaticaanstad
    # niet getoetst wordt, mag Italië geen bevinding opleveren.
    heilige_stoel = maak_record(
        locationkey="vaticaanstad",
        location="Vaticaanstad",
        isocode="VAT",
        representations=[maak_vertegenwoordiging(id="ambassade-vaticaanstad")],
    )
    italie = maak_record(
        locationkey="italie",
        location="Italië",
        isocode="ITA",
        representations=[maak_vertegenwoordiging(id="ambassade-vaticaanstad", address=[""])],
    )
    settings = Settings(
        excluded_countries=frozenset({"vaticaanstad"}),
        thresholds=Thresholds(min_aantal_reisadviezen=1),
    )

    rapport = run_rules(maak_snapshot([heilige_stoel, italie]), settings)

    assert [f.rule_id for f in rapport.findings if f.severity is not Severity.INFO] == []


def test_uitsluiting_werkt_ook_op_een_oudere_snapshot():
    volledig = maak_snapshot(
        [
            maak_record(),
            maak_record(locationkey="vaticaanstad", location="Vaticaanstad", isocode="ZZZ"),
        ]
    )
    settings = Settings(
        excluded_countries=frozenset({"vaticaanstad"}),
        thresholds=Thresholds(min_aantal_reisadviezen=1),
    )

    rapport = run_rules(volledig, settings)

    assert rapport.countries_checked == 1
    assert rapport.findings == []


def test_f03_zwijgt_over_een_uitgesloten_land():
    zonder_advies = maak_snapshot(
        [maak_record(locationkey="vaticaanstad", location="Vaticaanstad")], traveladvice_index=[]
    )
    settings = Settings(
        excluded_countries=frozenset({"vaticaanstad"}),
        thresholds=Thresholds(min_aantal_reisadviezen=0),
    )

    rapport = run_rules(zonder_advies, settings)

    assert [f.rule_id for f in rapport.findings] == []


def test_adres_van_een_post_in_een_ander_land_wordt_gevonden():
    # Dezelfde post onder twee landen: alleen het thuisland draagt het adres.
    thuis = maak_record(
        locationkey="nieuw-zeeland",
        location="Nieuw-Zeeland",
        isocode="NZL",
        representations=[maak_vertegenwoordiging(id="ambassade-wellington")],
    )
    bediend = maak_record(
        locationkey="amerikaans-samoa",
        location="Amerikaans-Samoa",
        isocode="ASM",
        representations=[maak_vertegenwoordiging(id="ambassade-wellington", address=[""])],
    )

    snapshot = maak_snapshot([thuis, bediend])
    resolve_addresses(snapshot)

    assert bediend.address_elsewhere == {"ambassade-wellington": "Nieuw-Zeeland"}
    assert thuis.address_elsewhere == {}


def test_een_post_zonder_adres_waar_dan_ook_blijft_gemeld():
    gesloten = maak_record(
        representations=[maak_vertegenwoordiging(id="ambassade-kaboel", address=[""])]
    )
    snapshot = maak_snapshot([gesloten])

    resolve_addresses(snapshot)

    assert gesloten.address_elsewhere == {}
    rapport = run_rules(snapshot, Settings(thresholds=Thresholds(min_aantal_reisadviezen=1)))
    assert [f.rule_id for f in rapport.findings] == ["L18"]


def test_run_rules_legt_de_koppeling_ook_bij_een_oudere_snapshot():
    # Een snapshot van vóór deze functie draagt het veld nog niet.
    thuis = maak_record(
        locationkey="nieuw-zeeland",
        location="Nieuw-Zeeland",
        isocode="NZL",
        representations=[maak_vertegenwoordiging(id="ambassade-wellington")],
    )
    bediend = maak_record(
        locationkey="amerikaans-samoa",
        location="Amerikaans-Samoa",
        isocode="ASM",
        representations=[maak_vertegenwoordiging(id="ambassade-wellington", address=[""])],
    )

    rapport = run_rules(
        maak_snapshot([thuis, bediend]),
        Settings(thresholds=Thresholds(min_aantal_reisadviezen=1)),
    )

    assert [f.rule_id for f in rapport.findings if f.severity is not Severity.INFO] == []


def test_de_link_naar_een_ander_land_geldt_als_adres():
    # Ook als dat andere land helemaal niet is opgehaald: de link is er, dus
    # het adres staat erachter.
    bediend = maak_record(
        locationkey="amerikaans-samoa",
        location="Amerikaans-Samoa",
        isocode="ASM",
        representations=[
            maak_vertegenwoordiging(
                id="ambassade-wellington",
                address=[""],
                dataurl="https://opendata.nederlandwereldwijd.nl/v2/sources/nederlandwereldwijd"
                "/infotypes/countries/nzl/nl-representation/ambassade-wellington",
            )
        ],
    )

    snapshot = maak_snapshot([bediend])
    resolve_addresses(snapshot)

    assert bediend.address_elsewhere == {"ambassade-wellington": "NZL"}
    rapport = run_rules(snapshot, Settings(thresholds=Thresholds(min_aantal_reisadviezen=1)))
    assert [f.rule_id for f in rapport.findings if f.severity is not Severity.INFO] == []


def test_de_naam_van_het_andere_land_wordt_gebruikt_als_dat_bekend_is():
    thuis = maak_record(
        locationkey="nieuw-zeeland", location="Nieuw-Zeeland", isocode="NZL",
        representations=[maak_vertegenwoordiging(id="ambassade-wellington")],
    )
    bediend = maak_record(
        locationkey="amerikaans-samoa", location="Amerikaans-Samoa", isocode="ASM",
        representations=[
            maak_vertegenwoordiging(
                id="ambassade-wellington",
                address=[""],
                dataurl=".../infotypes/countries/nzl/nl-representation/ambassade-wellington",
            )
        ],
    )

    snapshot = maak_snapshot([thuis, bediend])
    resolve_addresses(snapshot)

    assert bediend.address_elsewhere == {"ambassade-wellington": "Nieuw-Zeeland"}


def test_een_post_die_naar_zichzelf_verwijst_blijft_gemeld():
    # Kaboel: de dataurl wijst naar het eigen land en er zijn geen adresregels.
    gesloten = maak_record(
        locationkey="afghanistan", location="Afghanistan", isocode="AFG",
        representations=[
            maak_vertegenwoordiging(
                id="ambassade-kaboel",
                address=[""],
                dataurl=".../infotypes/countries/afg/nl-representation/ambassade-kaboel",
            )
        ],
    )

    snapshot = maak_snapshot([gesloten])
    resolve_addresses(snapshot)

    assert gesloten.address_elsewhere == {}
    rapport = run_rules(snapshot, Settings(thresholds=Thresholds(min_aantal_reisadviezen=1)))
    assert [f.rule_id for f in rapport.findings] == ["L18"]
