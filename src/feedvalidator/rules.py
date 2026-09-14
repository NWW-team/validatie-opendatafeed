"""De validatieregels waaraan de opendatafeed getoetst wordt.

Elke regel is klein en losstaand: hij krijgt één land (of de hele feed) en
levert nul of meer bevindingen op. Zo blijft het rapport herleidbaar tot een
concrete regel, wat precies is wat de discussie CMS-vs-feed-vs-afnemer nodig
heeft.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any
from urllib.parse import urlparse

from .config import Settings
from .isocodes import is_known_alpha3
from .models import CountryRecord, FeedSnapshot, Finding, Severity
from .parsing import (
    as_text,
    modification_date,
    parse_iso_datetime,
    strip_html,
    validity_date,
)

CountryCheck = Callable[[CountryRecord, Settings], Iterable[Finding]]
FeedCheck = Callable[[FeedSnapshot, Settings], Iterable[Finding]]


@dataclass(frozen=True)
class Rule:
    """Een validatieregel met zijn metadata."""

    id: str
    title: str
    description: str
    severity: Severity
    scope: str  # "feed" of "land"
    check: CountryCheck | FeedCheck
    #: Regel draait alleen als deze instelling aanstaat.
    requires: str | None = None


FEED_RULES: list[Rule] = []
COUNTRY_RULES: list[Rule] = []


def feed_rule(
    rule_id: str, title: str, description: str, severity: Severity, requires: str | None = None
):
    def decorator(func: FeedCheck) -> FeedCheck:
        FEED_RULES.append(Rule(rule_id, title, description, severity, "feed", func, requires))
        return func

    return decorator


def country_rule(
    rule_id: str, title: str, description: str, severity: Severity, requires: str | None = None
):
    def decorator(func: CountryCheck) -> CountryCheck:
        COUNTRY_RULES.append(Rule(rule_id, title, description, severity, "land", func, requires))
        return func

    return decorator


def _finding(
    rule: Rule, message: str, record: CountryRecord | None = None, **detail: Any
) -> Finding:
    return Finding(
        rule_id=rule.id,
        rule_title=rule.title,
        severity=rule.severity,
        message=message,
        location=record.location if record else None,
        isocode=record.isocode if record else None,
        detail=detail,
    )


def rule_by_id(rule_id: str) -> Rule:
    for rule in FEED_RULES + COUNTRY_RULES:
        if rule.id == rule_id:
            return rule
    raise KeyError(rule_id)


def _make(
    rule_id: str, message: str, record: CountryRecord | None = None, **detail: Any
) -> Finding:
    return _finding(rule_by_id(rule_id), message, record, **detail)


def _today() -> date:
    return datetime.now(UTC).date()


# --------------------------------------------------------------------------
# Regels over de feed als geheel
# --------------------------------------------------------------------------


@feed_rule(
    "F01",
    "Alle feed-endpoints zijn bereikbaar",
    "De lijst-endpoints voor landen, reisadviezen, vertegenwoordigingen en "
    "hulp bij nood moeten alle vier antwoorden.",
    Severity.ERROR,
)
def check_endpoints(snapshot: FeedSnapshot, settings: Settings) -> Iterator[Finding]:
    for endpoint, error in sorted(snapshot.fetch_errors.items()):
        yield _make("F01", f"Endpoint {endpoint} is niet op te halen: {error}", endpoint=endpoint)


@feed_rule(
    "F02",
    "De feed bevat voldoende reisadviezen",
    "Het aantal reisadviezen mag niet onder de ondergrens zakken; een plotse "
    "daling wijst op een publicatieprobleem.",
    Severity.ERROR,
)
def check_advice_count(snapshot: FeedSnapshot, settings: Settings) -> Iterator[Finding]:
    aantal = len(snapshot.traveladvice_index)
    ondergrens = settings.thresholds.min_aantal_reisadviezen
    if aantal < ondergrens:
        yield _make(
            "F02",
            f"De feed bevat {aantal} reisadviezen, minder dan de ondergrens van {ondergrens}.",
            aantal=aantal,
            ondergrens=ondergrens,
        )


@feed_rule(
    "F03",
    "Ieder land in de feed heeft een reisadvies",
    "Elk land uit /infotypes/countries hoort terug te komen in de "
    "reisadviezenindex; ontbreekt het daar, dan ziet een afnemer het land niet.",
    Severity.ERROR,
)
def check_coverage(snapshot: FeedSnapshot, settings: Settings) -> Iterator[Finding]:
    met_advies = {as_text(item.get("locationkey")) for item in snapshot.traveladvice_index}
    for country in snapshot.countries:
        key = as_text(country.get("locationkey"))
        if key and key not in met_advies:
            yield _make(
                "F03",
                f"Land {as_text(country.get('location')) or key} staat wel in de landenlijst, "
                "maar heeft geen reisadvies in de index.",
                locationkey=key,
                isocode=as_text(country.get("isocode")),
            )


@feed_rule(
    "F04",
    "Elk reisadvies hoort bij een bekend land",
    "Een reisadvies zonder bijbehorend land in /infotypes/countries is een wees "
    "en kan bij afnemers niet worden opgezocht.",
    Severity.WARNING,
)
def check_orphan_advice(snapshot: FeedSnapshot, settings: Settings) -> Iterator[Finding]:
    landen = {as_text(item.get("locationkey")) for item in snapshot.countries}
    for advice in snapshot.traveladvice_index:
        key = as_text(advice.get("locationkey"))
        if key and key not in landen:
            yield _make(
                "F04",
                f"Reisadvies '{as_text(advice.get('location')) or key}' hoort bij geen enkel "
                "land uit de landenlijst.",
                locationkey=key,
            )


@feed_rule(
    "F05",
    "Landcodes en landsleutels zijn uniek",
    "Dubbele ISO-codes of locationkeys leiden bij afnemers tot overschreven of "
    "verdwenen landen.",
    Severity.ERROR,
)
def check_unique_keys(snapshot: FeedSnapshot, settings: Settings) -> Iterator[Finding]:
    for veld, label in (("isocode", "ISO-code"), ("locationkey", "landsleutel")):
        gezien: dict[str, int] = {}
        for country in snapshot.countries:
            waarde = as_text(country.get(veld))
            if waarde:
                gezien[waarde] = gezien.get(waarde, 0) + 1
        for waarde, aantal in sorted(gezien.items()):
            if aantal > 1:
                yield _make(
                    "F05",
                    f"{label} '{waarde}' komt {aantal} keer voor in de landenlijst.",
                    veld=veld,
                    waarde=waarde,
                    aantal=aantal,
                )


@feed_rule(
    "F06",
    "De hulp-bij-nood artikelen staan in de feed",
    "De noodartikelen worden door de Reisapp getoond; een lege lijst valt "
    "direct op bij reizigers in nood.",
    Severity.WARNING,
)
def check_emergency_info(snapshot: FeedSnapshot, settings: Settings) -> Iterator[Finding]:
    if not snapshot.emergency_info:
        yield _make("F06", "De feed levert geen enkel hulp-bij-nood artikel.")


@feed_rule(
    "F07",
    "Contactvelden van vertegenwoordigingen komen door de feed heen",
    "Een veld dat bij álle vertegenwoordigingen leeg is, is geen redactionele "
    "omissie maar een gat in de feed zelf — precies het onderscheid dat de "
    "discussie CMS-vs-feed-vs-afnemer nodig heeft.",
    Severity.WARNING,
)
def check_contact_fields(snapshot: FeedSnapshot, settings: Settings) -> Iterator[Finding]:
    velden = {
        "telefoonnummer": ("telephonenumbers", "phonenumbers"),
        "e-mailadres": ("emailaddress", "emailaddresses"),
        "noodnummer": ("emergencynumber",),
    }
    vertegenwoordigingen = [v for record in snapshot.records for v in record.representations]
    if not vertegenwoordigingen:
        return
    for label, sleutels in velden.items():
        gevuld = sum(
            1 for v in vertegenwoordigingen if any(as_text(v.get(sleutel)) for sleutel in sleutels)
        )
        if gevuld == 0:
            yield _make(
                "F07",
                f"Het veld {label} is bij alle {len(vertegenwoordigingen)} vertegenwoordigingen "
                "leeg; de feed levert dit gegeven niet.",
                veld=label,
                sleutels=list(sleutels),
                totaal=len(vertegenwoordigingen),
            )


# --------------------------------------------------------------------------
# Regels per land
# --------------------------------------------------------------------------


@country_rule(
    "L01",
    "Het reisadvies van het land is op te halen",
    "Het detail-endpoint van het reisadvies moet antwoorden; zonder detail ziet "
    "een afnemer wel het land, maar geen advies.",
    Severity.ERROR,
)
def check_advice_fetch(record: CountryRecord, settings: Settings) -> Iterator[Finding]:
    error = record.fetch_errors.get("traveladvice")
    if error:
        yield _make("L01", f"Reisadvies is niet op te halen: {error}", record)


@country_rule(
    "L02",
    "Het land heeft een geldige ISO 3166-1 alpha-3 code",
    "De ISO-code is voor afnemers de sleutel om land en advies te koppelen.",
    Severity.ERROR,
)
def check_isocode(record: CountryRecord, settings: Settings) -> Iterator[Finding]:
    code = (record.isocode or "").strip()
    if not code:
        yield _make("L02", "Het land heeft geen ISO-code.", record)
        return
    if code in settings.extra_isocodes:
        return
    if len(code) != 3 or not code.isalpha() or not code.isupper():
        yield _make(
            "L02",
            f"ISO-code '{code}' heeft niet de vorm van drie hoofdletters.",
            record,
            code=code,
        )
        return
    if not is_known_alpha3(code):
        yield _make(
            "L02", f"ISO-code '{code}' staat niet in ISO 3166-1 alpha-3.", record, code=code
        )


@country_rule(
    "L03",
    "De ISO-code in het reisadvies is gelijk aan die van het land",
    "Wijken land en reisadvies af, dan koppelt een afnemer het advies aan het "
    "verkeerde land.",
    Severity.ERROR,
)
def check_isocode_consistency(record: CountryRecord, settings: Settings) -> Iterator[Finding]:
    if not record.traveladvice:
        return
    advies_code = as_text(record.traveladvice.get("isocode"))
    if advies_code and record.isocode and advies_code != record.isocode:
        yield _make(
            "L03",
            f"Het land heeft ISO-code '{record.isocode}', het reisadvies '{advies_code}'.",
            record,
            land=record.isocode,
            reisadvies=advies_code,
        )


@country_rule(
    "L04",
    "Het reisadvies heeft een titel",
    "De titel wordt door afnemers als kop getoond.",
    Severity.ERROR,
)
def check_title(record: CountryRecord, settings: Settings) -> Iterator[Finding]:
    if record.traveladvice is not None and not as_text(record.traveladvice.get("title")):
        yield _make("L04", "Het reisadvies heeft een lege titel.", record)


@country_rule(
    "L05",
    "Het reisadvies heeft een gevulde introductie",
    "De introductie ('In het kort') is de samenvatting die de Reisapp en de "
    "informatieservice tonen.",
    Severity.WARNING,
)
def check_introduction(record: CountryRecord, settings: Settings) -> Iterator[Finding]:
    if record.traveladvice is None:
        return
    tekst = strip_html(record.traveladvice.get("introduction"))
    minimum = settings.thresholds.min_introductie_lengte
    if not tekst:
        yield _make("L05", "Het reisadvies heeft geen introductie.", record)
    elif len(tekst) < minimum:
        yield _make(
            "L05",
            f"De introductie is met {len(tekst)} tekens korter dan de ondergrens van {minimum}.",
            record,
            lengte=len(tekst),
            ondergrens=minimum,
        )


@country_rule(
    "L06",
    "Het reisadvies bevat inhoudelijke tekstblokken",
    "Zonder categorieën met tekstblokken is het advies leeg, ook al bestaat het "
    "record wel.",
    Severity.ERROR,
)
def check_content(record: CountryRecord, settings: Settings) -> Iterator[Finding]:
    if record.traveladvice is None:
        return
    categorieen = record.traveladvice.get("content") or []
    blokken = [
        blok
        for categorie in categorieen
        if isinstance(categorie, dict)
        for blok in (categorie.get("contentblocks") or [])
    ]
    if not categorieen:
        yield _make("L06", "Het reisadvies bevat geen enkele inhoudscategorie.", record)
    elif not blokken:
        yield _make(
            "L06",
            f"Het reisadvies heeft {len(categorieen)} categorie(ën) zonder enig tekstblok.",
            record,
            categorieen=len(categorieen),
        )


@country_rule(
    "L07",
    "Geen lege tekstblokken in het reisadvies",
    "Een blok met een kop maar zonder tekst laat bij afnemers een gat vallen.",
    Severity.WARNING,
)
def check_empty_blocks(record: CountryRecord, settings: Settings) -> Iterator[Finding]:
    if record.traveladvice is None:
        return
    for categorie in record.traveladvice.get("content") or []:
        if not isinstance(categorie, dict):
            continue
        naam = as_text(categorie.get("category")) or "(naamloze categorie)"
        for blok in categorie.get("contentblocks") or []:
            if not isinstance(blok, dict):
                continue
            titel = as_text(blok.get("paragraphtitle")) or "(naamloos blok)"
            if not strip_html(blok.get("paragraph")):
                yield _make(
                    "L07",
                    f"Tekstblok '{titel}' in categorie '{naam}' is leeg.",
                    record,
                    categorie=naam,
                    blok=titel,
                )


@country_rule(
    "L08",
    "Bij het reisadvies hoort een kaart",
    "De kaart hoort bij het advies; ontbreekt hij, dan toont de Reisapp een "
    "advies zonder kleurvlakken.",
    Severity.ERROR,
)
def check_map_present(record: CountryRecord, settings: Settings) -> Iterator[Finding]:
    if record.traveladvice is None:
        return
    kaarten = _map_files(record.traveladvice)
    if not kaarten:
        yield _make("L08", "Bij het reisadvies zit geen enkel kaartbestand.", record)


@country_rule(
    "L09",
    "Kaartbestanden zijn compleet beschreven",
    "Zonder URL, mimetype of omvang kan een afnemer de kaart niet betrouwbaar "
    "ophalen of cachen.",
    Severity.WARNING,
)
def check_map_metadata(record: CountryRecord, settings: Settings) -> Iterator[Finding]:
    if record.traveladvice is None:
        return
    for bestand in _map_files(record.traveladvice):
        naam = as_text(bestand.get("filename")) or "(naamloos bestand)"
        ontbreekt = [
            veld
            for veld in ("fileurl", "mimetype", "filesize")
            if not as_text(bestand.get(veld))
        ]
        if ontbreekt:
            yield _make(
                "L09",
                f"Kaart '{naam}' mist de velden: {', '.join(ontbreekt)}.",
                record,
                bestand=naam,
                ontbrekende_velden=ontbreekt,
            )


@country_rule(
    "L10",
    "Kaartbestanden zijn daadwerkelijk op te halen",
    "De kaart-URL moet een afbeelding opleveren; een dode link ziet een afnemer "
    "pas als de gebruiker klaagt.",
    Severity.ERROR,
    requires="check_files",
)
def check_map_reachable(record: CountryRecord, settings: Settings) -> Iterator[Finding]:
    for probe in record.map_checks:
        if probe.get("ok"):
            continue
        yield _make(
            "L10",
            f"Kaart '{probe.get('filename') or probe.get('url')}' is niet op te halen "
            f"({probe.get('reden')}).",
            record,
            **probe,
        )


@country_rule(
    "L11",
    "Het reisadvies heeft een leesbare wijzigingsdatum",
    "De wijzigingsdatum is het eerste wat een afnemer toont en waarop een "
    "melding 'dit advies is oud' wordt gebaseerd.",
    Severity.ERROR,
)
def check_modification_date(record: CountryRecord, settings: Settings) -> Iterator[Finding]:
    if record.traveladvice is None:
        return
    ruw = as_text(record.traveladvice.get("modificationdate"))
    if not ruw:
        yield _make("L11", "Het reisadvies heeft geen wijzigingsdatum.", record)
        return
    if modification_date(ruw) is None:
        yield _make("L11", f"De wijzigingsdatum is niet te lezen: '{ruw}'.", record, waarde=ruw)


@country_rule(
    "L12",
    "De technische en de getoonde wijzigingsdatum komen overeen",
    "Het veld lastmodified stuurt caches aan, de tekst stuurt de gebruiker aan; "
    "lopen ze uiteen, dan ziet een afnemer een andere datum dan de website.",
    Severity.WARNING,
)
def check_modification_consistency(record: CountryRecord, settings: Settings) -> Iterator[Finding]:
    if record.traveladvice is None:
        return
    getoond = modification_date(as_text(record.traveladvice.get("modificationdate")))
    technisch = parse_iso_datetime(as_text(record.traveladvice.get("lastmodified")))
    if getoond is None or technisch is None:
        if technisch is None and as_text(record.traveladvice.get("lastmodified")):
            yield _make(
                "L12",
                f"Het veld lastmodified is geen geldige timestamp: "
                f"'{as_text(record.traveladvice.get('lastmodified'))}'.",
                record,
            )
        return
    if technisch.date() != getoond:
        yield _make(
            "L12",
            f"De getoonde wijzigingsdatum is {getoond:%d-%m-%Y}, maar lastmodified staat op "
            f"{technisch.date():%d-%m-%Y}.",
            record,
            getoond=getoond.isoformat(),
            lastmodified=technisch.isoformat(),
        )


@country_rule(
    "L13",
    "Het reisadvies is niet in de toekomst gedateerd",
    "Een datum in de toekomst wijst op een verkeerd ingestelde publicatiedatum "
    "in het CMS.",
    Severity.ERROR,
)
def check_future_date(record: CountryRecord, settings: Settings) -> Iterator[Finding]:
    if record.traveladvice is None:
        return
    vandaag = _today()
    technisch = parse_iso_datetime(as_text(record.traveladvice.get("lastmodified")))
    if technisch and technisch.date() > vandaag:
        yield _make(
            "L13",
            f"Het reisadvies is gedateerd op {technisch.date():%d-%m-%Y}, in de toekomst.",
            record,
            lastmodified=technisch.isoformat(),
        )


@country_rule(
    "L14",
    "De geldigheidsdatum is aanwezig en recent",
    "'Nog steeds geldig op' laat zien dat iemand het advies onlangs heeft "
    "nagelopen; loopt die datum achter, dan is het advies mogelijk verouderd.",
    Severity.WARNING,
)
def check_validity(record: CountryRecord, settings: Settings) -> Iterator[Finding]:
    if record.traveladvice is None:
        return
    ruw = as_text(record.traveladvice.get("modificationdate"))
    if not ruw:
        return
    geldig = validity_date(ruw)
    if geldig is None:
        yield _make("L14", f"Er staat geen geldigheidsdatum in '{ruw}'.", record, waarde=ruw)
        return
    ouderdom = (_today() - geldig).days
    grens = settings.thresholds.geldigheid_max_dagen
    if ouderdom > grens:
        yield _make(
            "L14",
            f"Het advies is voor het laatst geldig verklaard op {geldig:%d-%m-%Y}, "
            f"{ouderdom} dagen geleden (grens: {grens}).",
            record,
            geldig_op=geldig.isoformat(),
            ouderdom_dagen=ouderdom,
            grens_dagen=grens,
        )


@country_rule(
    "L15",
    "Het reisadvies is de afgelopen periode gewijzigd",
    "Een advies dat heel lang niet is aangeraakt verdient aandacht van de "
    "redactie.",
    Severity.INFO,
)
def check_staleness(record: CountryRecord, settings: Settings) -> Iterator[Finding]:
    if record.traveladvice is None:
        return
    technisch = parse_iso_datetime(as_text(record.traveladvice.get("lastmodified")))
    if technisch is None:
        return
    ouderdom = (_today() - technisch.date()).days
    grens = settings.thresholds.wijziging_max_dagen
    if ouderdom > grens:
        yield _make(
            "L15",
            f"Het reisadvies is al {ouderdom} dagen niet gewijzigd (grens: {grens}).",
            record,
            lastmodified=technisch.isoformat(),
            ouderdom_dagen=ouderdom,
        )


@country_rule(
    "L16",
    "Het reisadvies verwijst naar de juiste publiekspagina",
    "De canonical-URL is de brug tussen feed en website; klopt hij niet, dan "
    "verwijst een afnemer naar een pagina die niet bestaat.",
    Severity.WARNING,
)
def check_canonical(record: CountryRecord, settings: Settings) -> Iterator[Finding]:
    if record.traveladvice is None:
        return
    canonical = as_text(record.traveladvice.get("canonical"))
    if not canonical:
        yield _make("L16", "Het reisadvies heeft geen canonical-URL.", record)
        return
    parsed = urlparse(canonical)
    verwachte_host = urlparse(settings.website_base_url).netloc
    if parsed.scheme != "https" or parsed.netloc != verwachte_host:
        yield _make(
            "L16",
            f"De canonical-URL wijst niet naar https://{verwachte_host}: {canonical}",
            record,
            canonical=canonical,
        )


@country_rule(
    "L17",
    "Het land heeft een Nederlandse vertegenwoordiging in de feed",
    "Ambassade- en consulaatgegevens horen bij het reisadvies; ontbreken ze, "
    "dan ziet een reiziger geen contactmogelijkheid.",
    Severity.WARNING,
)
def check_representation_present(record: CountryRecord, settings: Settings) -> Iterator[Finding]:
    if record.fetch_errors.get("nl-representation"):
        yield _make(
            "L17",
            "Vertegenwoordigingen zijn niet op te halen: "
            f"{record.fetch_errors['nl-representation']}",
            record,
        )
        return
    if not record.representations:
        yield _make("L17", "Er staat geen Nederlandse vertegenwoordiging bij dit land.", record)


@country_rule(
    "L18",
    "Vertegenwoordigingen hebben een adres",
    "Een ambassade of consulaat zonder adres is voor een reiziger niet te "
    "vinden; het adres is het enige contactveld dat de feed per post vult.",
    Severity.WARNING,
)
def check_representation_address(record: CountryRecord, settings: Settings) -> Iterator[Finding]:
    for vertegenwoordiging in record.representations:
        naam = as_text(vertegenwoordiging.get("title")) or as_text(vertegenwoordiging.get("id"))
        if not as_text(vertegenwoordiging.get("address")):
            yield _make(
                "L18",
                f"Vertegenwoordiging '{naam}' heeft geen adres.",
                record,
                vertegenwoordiging=naam,
            )


@country_rule(
    "L19",
    "Feed en website tonen dezelfde wijzigingsdatum",
    "Dit is de directe controle op de vraag 'ligt het aan de feed of aan het "
    "afnemende systeem': toont de website iets anders, dan loopt de feed achter.",
    Severity.WARNING,
    requires="check_website",
)
def check_website_match(record: CountryRecord, settings: Settings) -> Iterator[Finding]:
    website = record.website
    if not website:
        return
    if website.get("error"):
        yield _make(
            "L19",
            f"De publiekspagina is niet op te halen: {website['error']}",
            record,
            url=website.get("url"),
        )
        return
    if record.traveladvice is None:
        return
    feed_datum = modification_date(as_text(record.traveladvice.get("modificationdate")))
    site_datum = website.get("modification_date")
    if feed_datum and site_datum and feed_datum.isoformat() != site_datum:
        yield _make(
            "L19",
            f"De feed noemt {feed_datum:%d-%m-%Y} als wijzigingsdatum, de website "
            f"{date.fromisoformat(site_datum):%d-%m-%Y}.",
            record,
            feed=feed_datum.isoformat(),
            website=site_datum,
            url=website.get("url"),
        )


def _map_files(traveladvice: dict[str, Any]) -> list[dict[str, Any]]:
    """De bestanden bij een reisadvies die als kaart tellen."""
    bestanden = traveladvice.get("files") or []
    return [
        bestand
        for bestand in bestanden
        if isinstance(bestand, dict)
        and (
            as_text(bestand.get("mapType"))
            or as_text(bestand.get("mimetype")).startswith("image/")
        )
    ]


def active_rules(settings: Settings) -> tuple[list[Rule], list[Rule]]:
    """De regels die bij deze instellingen daadwerkelijk draaien."""

    def actief(rule: Rule) -> bool:
        return rule.requires is None or bool(getattr(settings, rule.requires, False))

    return [r for r in FEED_RULES if actief(r)], [r for r in COUNTRY_RULES if actief(r)]


__all__ = [
    "Rule",
    "FEED_RULES",
    "COUNTRY_RULES",
    "active_rules",
    "rule_by_id",
    "_map_files",
]
