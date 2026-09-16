"""Rapportage: console, JSON, Markdown en een HTML-overzicht."""

from __future__ import annotations

import html
import json
from collections.abc import Iterable
from datetime import date
from importlib import resources
from pathlib import Path
from zoneinfo import ZoneInfo

from .models import Report, RuleResult, Severity
from .theme import CSS as THEME_CSS

_SEVERITY_VOLGORDE = {Severity.ERROR: 0, Severity.WARNING: 1, Severity.INFO: 2}

#: Bestandsnaam van de meegeleverde gebruikershandleiding, zowel voor de
#: link in het HTML-rapport als voor het bestand dat ernaast wordt gezet.
MANUAL_FILENAME = "gebruikershandleiding.pdf"

#: Het rapport wordt in Nederland gelezen, dus staat het peilmoment in
#: Nederlandse tijd. In UTC las het twee uur (zomertijd) of een uur
#: (wintertijd) vroeger dan de klok van de lezer, wat bij het naslaan van een
#: bevinding steevast tot de vraag leidde of het rapport wel van vandaag was.
#: De machineleesbare velden blijven UTC: rapport.json en de Supabase-tabel
#: houden hun ISO-8601-stempel met offset, zodat afnemers niets hoeven te raden.
_TIJDZONE = ZoneInfo("Europe/Amsterdam")


def _tijdstempel(report: Report) -> str:
    """Het peilmoment in Nederlandse tijd, met de tijdzone erbij genoemd."""
    lokaal = report.generated_at.astimezone(_TIJDZONE)
    return f"{lokaal:%d-%m-%Y %H:%M} (Nederlandse tijd)"


def _gesorteerd(results: Iterable[RuleResult]) -> list[RuleResult]:
    """Regels met bevindingen eerst, zwaarste bovenaan."""
    return sorted(
        results,
        key=lambda r: (r.ok, _SEVERITY_VOLGORDE[r.severity], -r.failed, r.rule_id),
    )


# -- console ---------------------------------------------------------------


def render_console(report: Report, max_findings: int = 5) -> str:
    """Een korte samenvatting voor de terminal."""
    lijnen: list[str] = []
    stempel = _tijdstempel(report)
    lijnen.append(f"Validatie opendatafeed — {stempel}")
    lijnen.append(f"Feed: {report.base_url}")
    lijnen.append(
        f"Landen gecontroleerd: {report.countries_checked} · "
        f"regels: {len(report.results)} · duur: {report.duration_seconds:.1f}s"
    )
    lijnen.append("")

    if report.excluded:
        lijnen.append(f"Buiten beschouwing gelaten: {', '.join(report.excluded)}")
        lijnen.append("")

    if report.closed_posts:
        lijnen.append(f"Als gesloten aangemerkt: {', '.join(report.closed_posts)}")
        lijnen.append("")

    if report.fetch_errors:
        lijnen.append("Endpoints die niet antwoordden:")
        for naam, fout in sorted(report.fetch_errors.items()):
            lijnen.append(f"  ! {naam}: {fout}")
        lijnen.append("")

    lijnen.append(
        f"Fouten: {report.errors} · waarschuwingen: {report.warnings} · info: {report.infos}"
    )
    lijnen.append("")

    for resultaat in _gesorteerd(report.results):
        merk = "OK  " if resultaat.ok else {"error": "FOUT", "warning": "WAAR", "info": "INFO"}[
            resultaat.severity.value
        ]
        lijnen.append(
            f"[{merk}] {resultaat.rule_id} {resultaat.title} "
            f"({resultaat.passed}/{resultaat.checked} in orde)"
        )
        for bevinding in resultaat.findings[:max_findings]:
            plaats = f"{bevinding.location} " if bevinding.location else ""
            lijnen.append(f"        - {plaats}{bevinding.message}")
        rest = resultaat.failed - max_findings
        if rest > 0:
            lijnen.append(f"        … en nog {rest} soortgelijke bevinding(en)")

    lijnen.append("")
    lijnen.append("Feed is gezond." if report.healthy else "Feed heeft blokkerende bevindingen.")
    return "\n".join(lijnen)


# -- json ------------------------------------------------------------------


def write_json(report: Report, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    return path


# -- markdown (o.a. voor de GitHub Actions samenvatting) -------------------


def render_markdown(report: Report, max_findings: int = 10) -> str:
    stempel = _tijdstempel(report)
    regels = [
        "# Validatie opendatafeed reisadviezen",
        "",
        f"**Peilmoment:** {stempel}  ",
        f"**Feed:** `{report.base_url}`  ",
        f"**Landen gecontroleerd:** {report.countries_checked}",
        "",
        "| Fouten | Waarschuwingen | Info | Regels met bevindingen |",
        "| ---: | ---: | ---: | ---: |",
        f"| {report.errors} | {report.warnings} | {report.infos} | "
        f"{report.rules_failed}/{len(report.results)} |",
        "",
    ]

    if report.excluded:
        regels += [
            f"**Buiten beschouwing gelaten:** {', '.join(report.excluded)}",
            "",
        ]

    if report.closed_posts:
        regels += [f"**Als gesloten aangemerkt:** {', '.join(report.closed_posts)}", ""]

    if report.fetch_errors:
        regels += ["## Endpoints die niet antwoordden", ""]
        regels += [f"- `{naam}`: {fout}" for naam, fout in sorted(report.fetch_errors.items())]
        regels.append("")

    regels += [
        "## Resultaat per regel",
        "",
        "| Regel | Onderwerp | Zwaarte | In orde | Bevindingen |",
        "| --- | --- | --- | ---: | ---: |",
    ]
    for resultaat in _gesorteerd(report.results):
        regels.append(
            f"| {resultaat.rule_id} | {resultaat.title} | {resultaat.severity.label} | "
            f"{resultaat.passed}/{resultaat.checked} | {resultaat.failed} |"
        )
    regels.append("")

    met_bevindingen = [r for r in _gesorteerd(report.results) if not r.ok]
    if met_bevindingen:
        regels += ["## Bevindingen", ""]
        for resultaat in met_bevindingen:
            regels.append(f"### {resultaat.rule_id} — {resultaat.title} ({resultaat.failed})")
            regels.append("")
            for bevinding in resultaat.findings[:max_findings]:
                plaats = f"**{bevinding.location}** — " if bevinding.location else ""
                regels.append(f"- {plaats}{bevinding.message}")
            rest = resultaat.failed - max_findings
            if rest > 0:
                regels.append(f"- _… en nog {rest} soortgelijke bevinding(en)_")
            regels.append("")
    return "\n".join(regels)


def write_markdown(report: Report, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_markdown(report), encoding="utf-8")
    return path


# -- html ------------------------------------------------------------------


def _esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def _variant(severity: Severity) -> str:
    return {"error": "error", "warning": "warning", "info": "info"}[severity.value]


def render_html(
    report: Report,
    max_findings: int = 50,
    theme_css: str | None = None,
    summary_only: bool = False,
) -> str:
    """Een HTML-rapport in de vormgeving van de Rijkshuisstijl Community.

    ``theme_css`` is de URL (of het pad) naar het stylesheet van het design
    system. Blijft die leeg, dan valt het rapport terug op de ingebouwde
    tokenwaarden en blijft het zonder netwerk leesbaar.

    ``summary_only`` laat alleen de meldbalk bovenaan staan — de statusmelding
    en de tegels met de aantallen. Al het overige (uitzonderingen, het
    resultaat per regel, en de bevindingen zelf) staat achter een verwijzing
    naar de afgeschermde weergave. Bedoeld voor de openbare Pages-pagina: die
    staat zonder inloggen open voor iedereen, dus een login ervoor beschermt
    pas iets als de openbare pagina zelf verder niets meer prijsgeeft.
    """
    stempel = _tijdstempel(report)
    gesorteerd = _gesorteerd(report.results)

    theme_link = (
        f'<link rel="stylesheet" href="{_esc(theme_css)}">\n' if theme_css else ""
    )

    tegels = [
        ("error", report.errors, "Fouten"),
        ("warning", report.warnings, "Waarschuwingen"),
        ("info", report.infos, "Informatief"),
        (
            "ok",
            f"{len(report.results) - report.rules_failed}/{len(report.results)}",
            "Regels zonder bevinding",
        ),
        ("ok", report.countries_checked, "Landen gecontroleerd"),
    ]
    tegel_html = "\n      ".join(
        f'<div class="rhc-data-summary__item rhc-data-summary__item--{variant}">'
        f'<div class="rhc-data-summary__value">{_esc(waarde)}</div>'
        f'<div class="rhc-data-summary__label">{_esc(label)}</div></div>'
        for variant, waarde, label in tegels
    )

    alert_variant = "ok" if report.healthy else "error"
    alert_tekst = (
        "Geen blokkerende bevindingen: de feed voldoet aan alle harde regels."
        if report.healthy
        else f"{report.errors} blokkerende bevinding(en): de feed voldoet niet aan "
        "alle harde regels."
    )

    excluded_html = ""
    if report.excluded:
        items = "".join(f"<li>{_esc(naam)}</li>" for naam in report.excluded)
        excluded_html = (
            '<h2 class="rhc-heading nl-heading--level-2">Buiten beschouwing gelaten</h2>'
            '<p class="nl-paragraph rhc-paragraph--rule">Deze landen zijn op verzoek niet '
            "getoetst; ze tellen niet mee in de aantallen hierboven.</p>"
            f'<ul class="rhc-unordered-list">{items}</ul>'
        )

    closed_html = ""
    if report.closed_posts:
        items = "".join(f"<li>{_esc(naam)}</li>" for naam in report.closed_posts)
        closed_html = (
            '<h2 class="rhc-heading nl-heading--level-2">Als gesloten aangemerkt</h2>'
            '<p class="nl-paragraph rhc-paragraph--rule">Deze posten zijn gesloten of '
            "opgeschort en hoeven daarom geen adres te hebben.</p>"
            f'<ul class="rhc-unordered-list">{items}</ul>'
        )

    fetch_html = ""
    if report.fetch_errors:
        items = "".join(
            f"<li><strong>{_esc(naam)}</strong> — {_esc(fout)}</li>"
            for naam, fout in sorted(report.fetch_errors.items())
        )
        fetch_html = (
            '<h2 class="rhc-heading nl-heading--level-2">Endpoints die niet antwoordden</h2>'
            f'<ul class="rhc-unordered-list">{items}</ul>'
        )

    rijen = "\n        ".join(
        "<tr>"
        f"<td>{_esc(r.rule_id)}</td>"
        f"<td>{_esc(r.title)}</td>"
        f'<td><span class="rhc-badge rhc-badge--{"ok" if r.ok else _variant(r.severity)}">'
        f'{"In orde" if r.ok else _esc(r.severity.label)}</span></td>'
        f'<td class="num">{r.passed}/{r.checked}</td>'
        f'<td class="num">{r.failed}</td>'
        "</tr>"
        for r in gesorteerd
    )

    if summary_only:
        body_html = (
            '<p class="nl-paragraph">Het resultaat per regel, de uitzonderingen en de '
            'bevindingen zelf — welk land, welke melding — staan achter een inlog met '
            'allowlist. <a class="rhc-link" href="toegang/">Ga naar de afgeschermde '
            "weergave</a>.</p>"
        )
    else:
        blokken = []
        for resultaat in gesorteerd:
            if resultaat.ok:
                continue
            items = []
            for bevinding in resultaat.findings[:max_findings]:
                plaats = (
                    f"<strong>{_esc(bevinding.location)}</strong> — " if bevinding.location else ""
                )
                items.append(f"<li>{plaats}{_esc(bevinding.message)}</li>")
            rest = resultaat.failed - max_findings
            if rest > 0:
                items.append(
                    f'<li class="rhc-empty">… en nog {rest} soortgelijke bevinding(en)</li>'
                )
            blokken.append(
                '<details class="rhc-accordion__section" open>'
                f"<summary>{_esc(resultaat.rule_id)} — {_esc(resultaat.title)} "
                f'<span class="rhc-badge rhc-badge--{_variant(resultaat.severity)}">'
                f"{resultaat.failed}</span></summary>"
                f'<p class="nl-paragraph rhc-paragraph--rule">{_esc(resultaat.description)}</p>'
                f'<ul class="rhc-unordered-list">{"".join(items)}</ul>'
                "</details>"
            )
        bevindingen_html = (
            "".join(blokken)
            if blokken
            else '<p class="nl-paragraph rhc-empty">Geen enkele regel leverde een bevinding op.</p>'
        )

        def _datumcel(waarde: date | None) -> str:
            return _esc(f"{waarde:%d-%m-%Y}") if waarde else '<span class="rhc-empty">—</span>'

        datums_rijen = "\n        ".join(
            "<tr>"
            f"<td>{_esc(d.location)}</td>"
            f"<td>{_esc(d.isocode)}</td>"
            f"<td>{_datumcel(d.shown)}</td>"
            f"<td>{_datumcel(d.modified)}</td>"
            f"<td>{_datumcel(d.pushed)}</td>"
            "</tr>"
            for d in report.date_overview
        )

        body_html = f"""{fetch_html}

    {excluded_html}

    <h2 class="rhc-heading nl-heading--level-2">Resultaat per regel</h2>
    <div class="rhc-table-wrapper">
      <table class="rhc-table">
        <thead><tr><th>Regel</th><th>Onderwerp</th><th>Status</th>
          <th class="num">In orde</th><th class="num">Bevindingen</th></tr></thead>
        <tbody>
        {rijen}
        </tbody>
      </table>
    </div>

    {closed_html}

    <h2 class="rhc-heading nl-heading--level-2">Bevindingen</h2>
    {bevindingen_html}

    <h2 class="rhc-heading nl-heading--level-2">Datums per land</h2>
    <p class="nl-paragraph rhc-paragraph--rule">De drie datums van elk land naast elkaar,
       zonder oordeel — regel L12 hierboven duidt alleen de afwijkingen.</p>
    <div class="rhc-table-wrapper">
      <table class="rhc-table">
        <thead><tr><th>Land</th><th>ISO</th><th>Getoond</th><th>Gewijzigd</th>
          <th>Gepusht</th></tr></thead>
        <tbody>
        {datums_rijen}
        </tbody>
      </table>
    </div>"""

    return f"""<!doctype html>
<html lang="nl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Validatie opendatafeed reisadviezen</title>
{theme_link}<style>{THEME_CSS}</style>
</head>
<body class="rhc-theme">
  <header class="rhc-page-header">
    <div class="rhc-page-header__inner rhc-page-header__row">
      <div>
        <h1 class="rhc-heading nl-heading--level-1">Validatie opendatafeed reisadviezen</h1>
        <p class="nl-paragraph rhc-paragraph--subtle">Ministerie van Buitenlandse Zaken ·
           Nederland Wereldwijd</p>
      </div>
      <a class="rhc-button" href="{_esc(MANUAL_FILENAME)}" download>Gebruikershandleiding (pdf)</a>
    </div>
  </header>

  <main class="rhc-page-content">
    <p class="nl-paragraph rhc-paragraph--subtle">Peilmoment {_esc(stempel)} ·
       feed <code>{_esc(report.base_url)}</code> · doorlooptijd {report.duration_seconds:.1f}s</p>

    <div class="rhc-alert rhc-alert--{alert_variant}">
      <div class="rhc-alert__body">{_esc(alert_tekst)}</div>
    </div>

    <div class="rhc-data-summary">
      {tegel_html}
    </div>

    {body_html}
  </main>

  <footer class="rhc-page-footer">
    <div class="rhc-page-footer__inner">
      Gegenereerd door feedvalidator · bron: opendatafeed Nederland Wereldwijd (CC0 1.0) ·
      vormgeving volgens de
      <a class="rhc-link"
         href="https://github.com/nl-design-system/rijkshuisstijl-community">Rijkshuisstijl
         Community</a>.
    </div>
  </footer>
</body>
</html>
"""


def write_html(
    report: Report,
    path: Path,
    theme_css: str | None = None,
    summary_only: bool = False,
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        render_html(report, theme_css=theme_css, summary_only=summary_only), encoding="utf-8"
    )
    return path


def write_manual(path: Path) -> Path:
    """Zet de meegeleverde gebruikershandleiding naast het HTML-rapport.

    De handleiding wordt met het pakket meegeleverd (``assets/``), zodat de
    downloadknop in het rapport altijd naar een bestaand bestand wijst —
    zowel lokaal als op de gepubliceerde Pages-pagina.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    bron = resources.files("feedvalidator").joinpath("assets", MANUAL_FILENAME)
    path.write_bytes(bron.read_bytes())
    return path
