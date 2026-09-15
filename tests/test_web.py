"""De statische afgeschermde weergave (web/) mag niet losraken van de code.

web/theme.css is een kopie van feedvalidator.theme.CSS — er is geen
buildstap die ze aan elkaar knoopt, dus zonder deze test zou een wijziging
in de een stilletjes uit de pas gaan lopen met de ander.
"""

from __future__ import annotations

from pathlib import Path

from feedvalidator.theme import CSS

WORTEL = Path(__file__).resolve().parents[1]


def test_web_theme_css_is_een_kopie_van_de_python_css():
    tekst = (WORTEL / "web" / "theme.css").read_text(encoding="utf-8")
    # web/theme.css begint met een uitlegcommentaar dat theme.py niet heeft;
    # de regels zelf, vanaf de eerste ".rhc-theme {", moeten gelijk zijn.
    kopie = tekst[tekst.index(".rhc-theme {") :]
    assert kopie.strip() == CSS.strip()
