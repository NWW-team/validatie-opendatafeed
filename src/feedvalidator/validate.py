"""Het ophalen van de feed en het draaien van de validatieregels."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from typing import Any

from .client import FeedClient, FeedError, RateLimitError
from .config import Settings
from .models import CountryRecord, FeedSnapshot, Report, RuleResult, Severity
from .parsing import as_text
from .rules import _map_files, active_rules
from .website import fetch_website_dates

logger = logging.getLogger(__name__)

#: Callback voor voortgang: (fase, gedaan, totaal).
Progress = Callable[[str, int, int], None]


def _noop(phase: str, done: int, total: int) -> None:  # pragma: no cover - triviaal
    return None


def fetch_snapshot(
    client: FeedClient, settings: Settings, progress: Progress = _noop
) -> FeedSnapshot:
    """Haal alles op wat de regels nodig hebben."""
    snapshot = FeedSnapshot(
        fetched_at=datetime.now(UTC),
        base_url=settings.base_url,
    )

    indexen = {
        "countries": client.list_countries,
        "traveladvice": client.list_traveladvice,
        "nl-representation": client.list_representations,
        "hulp-bij-nood": client.list_emergency_info,
    }
    for nummer, (naam, ophalen) in enumerate(indexen.items(), start=1):
        progress("index", nummer, len(indexen))
        try:
            waarde = ophalen()
        except FeedError as exc:
            snapshot.fetch_errors[naam] = str(exc)
            logger.warning("index %s mislukt: %s", naam, exc)
            continue
        if naam == "countries":
            snapshot.countries = waarde
        elif naam == "traveladvice":
            snapshot.traveladvice_index = waarde
        elif naam == "nl-representation":
            snapshot.representation_index = waarde
        else:
            snapshot.emergency_info = waarde

    # Ook uitgesloten landen worden opgehaald. Een uitsluiting betekent "dit
    # land beoordeel ik niet", niet "dit land bestaat niet": een post in een
    # uitgesloten land kan het adres dragen waar een ander land naar verwijst.
    # Het filteren gebeurt in run_rules.
    landen = snapshot.countries
    if settings.limit:
        landen = landen[: settings.limit]

    snapshot.records = [
        CountryRecord(
            locationkey=as_text(land.get("locationkey")),
            location=as_text(land.get("location")) or as_text(land.get("locationkey")),
            isocode=as_text(land.get("isocode")) or None,
            country=land,
        )
        for land in landen
    ]

    gedaan = 0
    totaal = len(snapshot.records)
    with ThreadPoolExecutor(max_workers=max(settings.workers, 1)) as pool:
        for _ in pool.map(lambda r: _enrich(client, r, settings), snapshot.records):
            gedaan += 1
            progress("landen", gedaan, totaal)

    resolve_addresses(snapshot)
    snapshot.rate_limited = client.rate_limited
    return snapshot


def _enrich(client: FeedClient, record: CountryRecord, settings: Settings) -> CountryRecord:
    """Vul één land aan met reisadvies, vertegenwoordigingen en extra checks."""
    if not record.locationkey:
        record.fetch_errors["traveladvice"] = "Het land heeft geen locationkey"
        return record

    try:
        record.traveladvice = client.get_traveladvice(record.locationkey)
    except RateLimitError as exc:
        record.fetch_errors["traveladvice"] = str(exc)
        record.rate_limited = True
    except FeedError as exc:
        record.fetch_errors["traveladvice"] = str(exc)

    try:
        index = client.get_representations(record.locationkey)
    except RateLimitError as exc:
        record.fetch_errors["nl-representation"] = str(exc)
        record.rate_limited = True
        index = []
    except FeedError as exc:
        record.fetch_errors["nl-representation"] = str(exc)
        index = []

    for vertegenwoordiging in index:
        rep_id = as_text(vertegenwoordiging.get("id"))
        if not rep_id:
            record.representations.append(vertegenwoordiging)
            continue
        try:
            record.representations.append(client.get_representation(record.locationkey, rep_id))
        except RateLimitError as exc:
            record.fetch_errors[f"nl-representation/{rep_id}"] = str(exc)
            record.rate_limited = True
            record.representations.append(vertegenwoordiging)
        except FeedError as exc:
            record.fetch_errors[f"nl-representation/{rep_id}"] = str(exc)
            record.representations.append(vertegenwoordiging)

    if settings.check_files and record.traveladvice:
        record.map_checks = _probe_maps(client, record.traveladvice)

    if settings.check_website and record.traveladvice:
        canonical = as_text(record.traveladvice.get("canonical"))
        if canonical:
            record.website = fetch_website_dates(client.session, canonical, settings)

    return record


def _probe_maps(client: FeedClient, traveladvice: dict[str, Any]) -> list[dict[str, Any]]:
    """Haal elke kaart op en leg vast of dat lukte."""
    probes: list[dict[str, Any]] = []
    for bestand in _map_files(traveladvice):
        url = as_text(bestand.get("fileurl"))
        naam = as_text(bestand.get("filename"))
        if not url:
            probes.append({"url": "", "filename": naam, "ok": False, "reden": "geen fileurl"})
            continue
        try:
            status, content_type, omvang = client.head_file(url)
        except Exception as exc:  # noqa: BLE001 - elke netwerkfout is hier een bevinding
            probes.append({"url": url, "filename": naam, "ok": False, "reden": str(exc)})
            continue
        if status != 200:
            reden = f"HTTP {status}"
        elif not content_type.startswith("image/"):
            reden = f"mimetype {content_type or 'onbekend'}"
        elif omvang == 0:
            reden = "leeg bestand"
        else:
            probes.append(
                {"url": url, "filename": naam, "ok": True, "status": status, "bytes": omvang}
            )
            continue
        probes.append({"url": url, "filename": naam, "ok": False, "reden": reden, "status": status})
    return probes


def resolve_addresses(snapshot: FeedSnapshot) -> None:
    """Zoek op welke vertegenwoordigingen hun adres bij een andere post hebben.

    Niet elk land heeft een eigen ambassade. Zo'n land krijgt in de feed een
    verwijzing naar de post die het bedient — hetzelfde ``id``, met een
    ``dataurl`` die naar het andere land wijst, maar zonder adresregels. Het
    adres staat dan bij dat andere land. Deze functie legt die koppeling, zodat
    een verwijzing niet als een ontbrekend adres wordt geteld.
    """
    met_adres: dict[str, str] = {}
    for record in snapshot.records:
        for vertegenwoordiging in record.representations:
            rep_id = as_text(vertegenwoordiging.get("id"))
            if rep_id and as_text(vertegenwoordiging.get("address")):
                met_adres.setdefault(rep_id, record.location or record.locationkey)

    for record in snapshot.records:
        elders = {}
        for vertegenwoordiging in record.representations:
            rep_id = as_text(vertegenwoordiging.get("id"))
            if not rep_id or as_text(vertegenwoordiging.get("address")):
                continue
            bron = met_adres.get(rep_id)
            if bron and bron != (record.location or record.locationkey):
                elders[rep_id] = bron
        record.address_elsewhere = elders


def run_rules(snapshot: FeedSnapshot, settings: Settings, duration: float = 0.0) -> Report:
    """Draai alle actieve regels over een snapshot."""
    # Ook bij --from-snapshot, zodat een oudere peiling dezelfde uitkomst geeft.
    resolve_addresses(snapshot)
    feed_rules, country_rules = active_rules(settings)
    records = [r for r in snapshot.records if r.locationkey not in settings.excluded_countries]
    results: list[RuleResult] = []

    for rule in feed_rules:
        findings = list(rule.check(snapshot, settings))
        results.append(
            RuleResult(
                rule_id=rule.id,
                title=rule.title,
                description=rule.description,
                severity=rule.severity,
                checked=1,
                findings=findings,
            )
        )

    for rule in country_rules:
        findings = []
        for record in records:
            findings.extend(rule.check(record, settings))
        results.append(
            RuleResult(
                rule_id=rule.id,
                title=rule.title,
                description=rule.description,
                severity=rule.severity,
                checked=len(records),
                findings=findings,
            )
        )

    results.sort(key=lambda r: r.rule_id)
    return Report(
        generated_at=snapshot.fetched_at,
        base_url=snapshot.base_url,
        duration_seconds=duration,
        countries_checked=len(records),
        results=results,
        fetch_errors=dict(snapshot.fetch_errors),
        excluded=_excluded_labels(snapshot, settings),
    )


def validate(
    settings: Settings, client: FeedClient | None = None, progress: Progress = _noop
) -> tuple[Report, FeedSnapshot]:
    """Haal de feed op en toets hem; geeft rapport én snapshot terug."""
    client = client or FeedClient(settings)
    start = time.monotonic()
    snapshot = fetch_snapshot(client, settings, progress)
    report = run_rules(snapshot, settings, duration=time.monotonic() - start)
    return report, snapshot


def _excluded_labels(snapshot: FeedSnapshot, settings: Settings) -> list[str]:
    """De uitgesloten landen met hun naam, zodat het rapport ze kan noemen."""
    namen = {
        as_text(land.get("locationkey")): as_text(land.get("location"))
        for land in snapshot.countries
    }
    return sorted(
        f"{namen[key]} ({key})" if namen.get(key) else key
        for key in settings.excluded_countries
    )


def exit_code(report: Report, fail_on: str) -> int:
    """Vertaal een rapport naar een exitcode voor CI."""
    if fail_on == "never":
        return 0
    if report.fetch_errors and fail_on in {"error", "warning"}:
        return 1
    if fail_on == "error":
        return 1 if report.count(Severity.ERROR) else 0
    if fail_on == "warning":
        return 1 if report.count(Severity.ERROR) or report.count(Severity.WARNING) else 0
    return 0
