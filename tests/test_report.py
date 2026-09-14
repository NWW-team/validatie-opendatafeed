"""Rapportage: console, JSON, Markdown en het HTML-rapport."""

from __future__ import annotations

import json

from conftest import maak_record, maak_snapshot
from feedvalidator.config import Settings, Thresholds
from feedvalidator.report import (
    render_console,
    render_html,
    render_markdown,
    write_html,
    write_json,
    write_markdown,
)
from feedvalidator.validate import run_rules

RUIM = Settings(thresholds=Thresholds(min_aantal_reisadviezen=1))


def rapport_met_bevinding():
    return run_rules(maak_snapshot([maak_record(isocode="ZZZ", representations=[])]), RUIM)


def schoon_rapport():
    return run_rules(maak_snapshot(), RUIM)


def test_console_noemt_de_aantallen_en_de_eerste_bevindingen():
    tekst = render_console(rapport_met_bevinding())
    assert "Fouten: 1" in tekst  # de onbekende ISO-code (L02)
    assert "L02" in tekst
    assert "ISO-code 'ZZZ'" in tekst
    assert "blokkerende bevindingen" in tekst


def test_console_meldt_een_gezonde_feed():
    assert "Feed is gezond." in render_console(schoon_rapport())


def test_console_kort_lange_lijsten_in():
    veel = run_rules(maak_snapshot([maak_record(isocode="ZZZ") for _ in range(9)]), RUIM)
    tekst = render_console(veel, max_findings=2)
    assert "en nog 7 soortgelijke bevinding(en)" in tekst


def test_json_bevat_de_samenvatting_en_alle_regels(tmp_path):
    pad = write_json(rapport_met_bevinding(), tmp_path / "rapport.json")
    data = json.loads(pad.read_text(encoding="utf-8"))

    assert data["summary"]["errors"] == 1
    assert data["summary"]["healthy"] is False
    assert {r["rule_id"] for r in data["results"]} >= {"F01", "L02", "L17"}
    iso = [r for r in data["results"] if r["rule_id"] == "L02"][0]
    assert iso["findings"][0]["severity"] == "error"


def test_markdown_heeft_een_tabel_en_bevindingen(tmp_path):
    tekst = render_markdown(rapport_met_bevinding())
    assert "| Regel | Onderwerp |" in tekst
    assert "## Bevindingen" in tekst
    assert "**Spanje**" in tekst
    assert write_markdown(rapport_met_bevinding(), tmp_path / "rapport.md").exists()


def test_html_gebruikt_de_rijkshuisstijl_opmaak():
    pagina = render_html(rapport_met_bevinding())
    assert '<body class="rhc-theme">' in pagina
    assert 'class="rhc-heading nl-heading--level-1"' in pagina
    assert "rhc-alert--error" in pagina
    assert "--rhc-color-donkerblauw-500" in pagina
    assert 'lang="nl"' in pagina


def test_html_toont_de_groene_melding_bij_een_schone_feed():
    pagina = render_html(schoon_rapport())
    assert "rhc-alert--ok" in pagina
    assert "Geen enkele regel leverde een bevinding op." in pagina


def test_html_markeert_een_regel_zonder_bevinding_als_in_orde():
    pagina = render_html(rapport_met_bevinding())
    assert '<span class="rhc-badge rhc-badge--ok">In orde</span>' in pagina
    assert '<span class="rhc-badge rhc-badge--error">Fout</span>' in pagina


def test_html_laadt_het_thema_alleen_als_erom_gevraagd_wordt():
    zonder = render_html(schoon_rapport())
    met = render_html(schoon_rapport(), theme_css="https://cdn.example/rhc.css")
    assert "<link rel=" not in zonder
    assert '<link rel="stylesheet" href="https://cdn.example/rhc.css">' in met


def test_html_ontsnapt_tekst_uit_de_feed():
    stout = maak_record(location="<script>alert(1)</script>", isocode="ZZZ")
    pagina = render_html(run_rules(maak_snapshot([stout]), RUIM))
    assert "<script>alert(1)</script>" not in pagina
    assert "&lt;script&gt;" in pagina


def test_html_wordt_weggeschreven(tmp_path):
    pad = write_html(schoon_rapport(), tmp_path / "sub" / "index.html")
    assert pad.exists() and pad.read_text(encoding="utf-8").startswith("<!doctype html>")
