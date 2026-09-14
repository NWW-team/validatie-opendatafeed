"""Datamodellen voor bevindingen en rapportage."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any


class Severity(StrEnum):
    """Hoe zwaar een bevinding weegt."""

    ERROR = "error"
    WARNING = "warning"
    INFO = "info"

    @property
    def label(self) -> str:
        return {"error": "Fout", "warning": "Waarschuwing", "info": "Info"}[self.value]


#: Volgorde waarin severities gesorteerd/gerapporteerd worden.
SEVERITY_ORDER = [Severity.ERROR, Severity.WARNING, Severity.INFO]


@dataclass
class Finding:
    """Eén afwijking die een regel heeft geconstateerd."""

    rule_id: str
    rule_title: str
    severity: Severity
    message: str
    location: str | None = None
    isocode: str | None = None
    detail: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["severity"] = self.severity.value
        return data


@dataclass
class CountryRecord:
    """Alles wat de feed over één land oplevert, bij elkaar."""

    locationkey: str
    location: str
    isocode: str | None
    #: Recordje uit /infotypes/countries.
    country: dict[str, Any] = field(default_factory=dict)
    #: Detailrecord uit /infotypes/countries/{land}/traveladvice.
    traveladvice: dict[str, Any] | None = None
    #: Lijst uit /infotypes/countries/{land}/nl-representation (detailrecords).
    representations: list[dict[str, Any]] = field(default_factory=list)
    #: Uitkomst van het opvragen van de kaartbestanden (--check-files).
    map_checks: list[dict[str, Any]] = field(default_factory=list)
    #: Vertegenwoordigingen die hun adres niet zelf dragen maar verwijzen naar
    #: een post in een ander land: id -> het land waar het adres wél staat.
    address_elsewhere: dict[str, str] = field(default_factory=dict)
    #: Wat de publiekssite toont, als --check-website aanstaat.
    website: dict[str, Any] | None = None
    #: Ophaalfouten per endpoint, zodat een regel niet over None struikelt.
    fetch_errors: dict[str, str] = field(default_factory=dict)
    #: Of een verzoek voor dit land is afgeknepen (HTTP 429). Dan zegt een
    #: ontbrekend reisadvies iets over ons tempo, niet over de feed.
    rate_limited: bool = False


@dataclass
class FeedSnapshot:
    """De opgehaalde feed van één moment."""

    fetched_at: datetime
    base_url: str
    countries: list[dict[str, Any]] = field(default_factory=list)
    traveladvice_index: list[dict[str, Any]] = field(default_factory=list)
    representation_index: list[dict[str, Any]] = field(default_factory=list)
    emergency_info: list[dict[str, Any]] = field(default_factory=list)
    records: list[CountryRecord] = field(default_factory=list)
    #: Fouten op feedniveau (endpoint onbereikbaar e.d.).
    fetch_errors: dict[str, str] = field(default_factory=dict)
    #: Aantal verzoeken dat de feed heeft afgeknepen (HTTP 429).
    rate_limited: int = 0


@dataclass
class RuleResult:
    """Uitkomst van één regel over de hele feed."""

    rule_id: str
    title: str
    description: str
    severity: Severity
    checked: int
    findings: list[Finding] = field(default_factory=list)

    @property
    def failed(self) -> int:
        return len(self.findings)

    @property
    def passed(self) -> int:
        return max(self.checked - self.failed, 0)

    @property
    def ok(self) -> bool:
        return not self.findings

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "title": self.title,
            "description": self.description,
            "severity": self.severity.value,
            "checked": self.checked,
            "passed": self.passed,
            "failed": self.failed,
            "ok": self.ok,
            "findings": [f.to_dict() for f in self.findings],
        }


@dataclass
class Report:
    """Het eindresultaat van een validatieronde."""

    generated_at: datetime
    base_url: str
    duration_seconds: float
    countries_checked: int
    results: list[RuleResult] = field(default_factory=list)
    fetch_errors: dict[str, str] = field(default_factory=dict)
    #: Landen die op verzoek buiten beschouwing zijn gelaten.
    excluded: list[str] = field(default_factory=list)

    @property
    def findings(self) -> list[Finding]:
        return [f for r in self.results for f in r.findings]

    def count(self, severity: Severity) -> int:
        return sum(1 for f in self.findings if f.severity is severity)

    @property
    def errors(self) -> int:
        return self.count(Severity.ERROR)

    @property
    def warnings(self) -> int:
        return self.count(Severity.WARNING)

    @property
    def infos(self) -> int:
        return self.count(Severity.INFO)

    @property
    def rules_failed(self) -> int:
        return sum(1 for r in self.results if not r.ok)

    @property
    def healthy(self) -> bool:
        return self.errors == 0 and not self.fetch_errors

    def to_dict(self) -> dict[str, Any]:
        return {
            "generated_at": self.generated_at.astimezone(UTC).isoformat(),
            "base_url": self.base_url,
            "duration_seconds": round(self.duration_seconds, 2),
            "countries_checked": self.countries_checked,
            "summary": {
                "rules": len(self.results),
                "rules_failed": self.rules_failed,
                "errors": self.errors,
                "warnings": self.warnings,
                "infos": self.infos,
                "healthy": self.healthy,
            },
            "fetch_errors": self.fetch_errors,
            "excluded": self.excluded,
            "results": [r.to_dict() for r in self.results],
        }
