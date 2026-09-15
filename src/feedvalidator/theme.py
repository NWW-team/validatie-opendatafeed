"""Vormgeving van het HTML-rapport volgens de Rijkshuisstijl Community.

Het rapport gebruikt de opmaak en klassenamen van het NL Design System /
Rijkshuisstijl Community (https://github.com/nl-design-system/rijkshuisstijl-community):
``rhc-theme`` als themaklasse, ``rhc-heading``/``nl-heading--level-*`` voor
koppen, ``rhc-alert`` voor de statusmelding en ``--rhc-*`` design tokens voor
kleur, ruimte en typografie.

Op het logo, de lettertypes en de kleuren van de Rijkshuisstijl rusten
auteursrechten; gebruik is voorbehouden aan de Rijksoverheid en aan partijen
die voor de Rijksoverheid werken. De huisstijlbestanden worden daarom *niet*
meegeleverd: het rapport verwijst naar het gepubliceerde pakket (zie
``--theme-css``) en valt zonder dat pakket terug op een kleine set
tokenwaarden, zodat een rapport in een CI-artefact ook zonder netwerk leesbaar
blijft.
"""

from __future__ import annotations

#: Standaard stylesheet van het design system. Leeg laten (of overschrijven met
#: een lokaal pad) wanneer de omgeving geen externe stylesheets mag laden.
DEFAULT_THEME_CSS = (
    "https://cdn.jsdelivr.net/npm/@rijkshuisstijl-community/design-tokens/dist/index.css"
)

#: Terugvalwaarden voor de design tokens die het rapport gebruikt. Ze staan
#: allemaal achter ``var(--rhc-…, fallback)``, dus zodra het echte pakket
#: geladen is, wint dat.
CSS = """
.rhc-theme {
  --app-font: var(--rhc-text-font-family-sans,
    "RijksSansVF", "Fira Sans", Arial, Verdana, sans-serif);
  --app-page: var(--rhc-color-cool-grey-50, oklch(98.415% 0.00341 247.86));
  --app-surface: var(--rhc-color-wit, oklch(100% 0 0));
  --app-text: var(--rhc-color-cool-grey-900, oklch(20.768% 0.03982 265.75));
  --app-muted: var(--rhc-color-cool-grey-600, oklch(44.553% 0.03745 257.28));
  --app-line: var(--rhc-color-cool-grey-300, oklch(86.898% 0.01985 252.89));
  --app-brand: var(--rhc-color-donkerblauw-500, oklch(49.37% 0.11351 240.39));
  --app-brand-text: var(--rhc-color-wit, oklch(100% 0 0));
  --app-lint: var(--rhc-color-lintblauw-500, oklch(37.619% 0.09695 253.44));
  --app-error: var(--rhc-color-rood-600, #9E1B16);
  --app-error-bg: var(--rhc-color-rood-50, oklch(92.432% 0.02892 22.962));
  --app-warning: var(--rhc-color-donkergeel-500, oklch(82.372% 0.1685 78.997));
  --app-warning-text: var(--rhc-color-cool-grey-900, oklch(20.768% 0.03982 265.75));
  --app-warning-bg: var(--rhc-color-donkergeel-50, oklch(96.925% 0.0348 87.074));
  --app-info: var(--rhc-color-hemelblauw-500, oklch(56.621% 0.1475 246.59));
  --app-info-bg: var(--rhc-color-hemelblauw-50, oklch(93.03% 0.02517 236.84));
  --app-ok: var(--rhc-color-groen-600, oklch(42.78% 0.1169 137.2));
  --app-ok-bg: var(--rhc-color-groen-50, oklch(93.217% 0.02714 134.97));
  --app-focus: var(--rhc-focus-outline-color, var(--rhc-color-zwart, oklch(0% 0 0)));
  --app-space-sm: var(--rhc-space-md, 0.5rem);
  --app-space-md: var(--rhc-space-xl, 1rem);
  --app-space-lg: var(--rhc-space-2xl, 1.5rem);
  --app-space-xl: var(--rhc-space-3xl, 2rem);
}

@media (prefers-color-scheme: dark) {
  .rhc-theme {
    --app-page: var(--rhc-color-cool-grey-50, oklch(10% 0.00341 247.86));
    --app-surface: var(--rhc-color-cool-grey-100, oklch(15% 0.00685 247.9));
    --app-text: var(--rhc-color-cool-grey-900, oklch(90% 0.03982 265.75));
    --app-muted: var(--rhc-color-cool-grey-700, oklch(75% 0.03916 257.29));
    --app-line: var(--rhc-color-cool-grey-400, oklch(40% 0.03511 256.79));
    --app-brand: var(--rhc-color-donkerblauw-200, oklch(20% 0.05961 229.57));
    --app-lint: var(--rhc-color-lintblauw-300, oklch(30% 0.05353 250.5));
    --app-error: var(--rhc-color-rood-500, oklch(65% 0.20669 29.543));
    --app-error-bg: var(--rhc-color-rood-100, oklch(15% 0.05903 22.29));
    --app-warning: var(--rhc-color-donkergeel-500, oklch(65% 0.1685 78.997));
    --app-warning-text: var(--rhc-color-cool-grey-900, oklch(90% 0.03982 265.75));
    --app-warning-bg: var(--rhc-color-donkergeel-100, oklch(15% 0.06747 86.64));
    --app-info: var(--rhc-color-hemelblauw-500, oklch(65% 0.1475 246.59));
    --app-info-bg: var(--rhc-color-hemelblauw-100, oklch(15% 0.04976 236.19));
    --app-ok: var(--rhc-color-groen-500, oklch(65% 0.16526 137.86));
    --app-ok-bg: var(--rhc-color-groen-100, oklch(15% 0.05573 133.62));
    --app-focus: var(--rhc-focus-inverse-outline-color, var(--rhc-color-wit, oklch(100% 0 0)));
  }
}

* { box-sizing: border-box; }

body.rhc-theme {
  margin: 0;
  background: var(--app-page);
  color: var(--app-text);
  font-family: var(--app-font);
  font-size: 1rem;
  line-height: 1.5;
}

:where(a, summary, details):focus-visible {
  outline: var(--rhc-focus-outline-width, 2px)
    var(--rhc-focus-outline-style, solid) var(--app-focus);
  outline-offset: var(--rhc-focus-outline-offset, 0.125rem);
}

.rhc-page-header {
  background: var(--app-brand);
  color: var(--app-brand-text);
  border-block-end: var(--rhc-size-quarter-lint, 0.75rem) solid var(--app-lint);
}

.rhc-page-header__inner,
.rhc-page-content,
.rhc-page-footer__inner {
  max-inline-size: 68rem;
  margin-inline: auto;
  padding-inline: var(--app-space-md);
}

.rhc-page-header__inner { padding-block: var(--app-space-lg); }
.rhc-page-header__row {
  display: flex; align-items: flex-start; justify-content: space-between;
  gap: var(--app-space-md); flex-wrap: wrap;
}
.rhc-page-content { padding-block: var(--app-space-xl) calc(var(--app-space-xl) * 2); }

.rhc-heading { font-family: var(--app-font); font-weight: 700; margin-block: 0; }
.nl-heading--level-1 { font-size: clamp(1.5rem, 1.2rem + 1.2vw, 2rem); }
.nl-heading--level-2 {
  font-size: clamp(1.25rem, 1.1rem + 0.6vw, 1.5rem);
  margin-block-start: var(--app-space-xl);
}
.nl-heading--level-3 { font-size: 1.125rem; }
.rhc-page-header .rhc-heading { color: var(--app-brand-text); }

.nl-paragraph { margin-block: var(--app-space-sm) 0; }
.rhc-paragraph--subtle { color: var(--app-muted); font-size: 0.9rem; }
.rhc-page-header .rhc-paragraph--subtle { color: var(--app-brand-text); opacity: 0.85; }

.rhc-alert {
  display: flex; gap: var(--app-space-md); align-items: flex-start;
  border-inline-start: 0.375rem solid var(--app-info);
  background: var(--app-info-bg);
  padding: var(--app-space-md);
  margin-block: var(--app-space-lg);
  border-radius: var(--rhc-border-radius-none, 0);
}
.rhc-alert--ok { border-color: var(--app-ok); background: var(--app-ok-bg); }
.rhc-alert--error { border-color: var(--app-error); background: var(--app-error-bg); }
.rhc-alert__body { font-weight: 600; }

.rhc-data-summary {
  display: grid; gap: var(--app-space-md); margin-block: var(--app-space-lg);
  grid-template-columns: repeat(auto-fit, minmax(9.5rem, 1fr));
}
.rhc-data-summary__item {
  background: var(--app-surface);
  border: 1px solid var(--app-line);
  padding: var(--app-space-md);
}
.rhc-data-summary__value { font-size: 2rem; font-weight: 700; line-height: 1.15; }
.rhc-data-summary__label { color: var(--app-muted); font-size: 0.85rem; }
.rhc-data-summary__item--error .rhc-data-summary__value { color: var(--app-error); }
.rhc-data-summary__item--warning .rhc-data-summary__value { color: var(--app-warning-text); }
.rhc-data-summary__item--info .rhc-data-summary__value { color: var(--app-info); }
.rhc-data-summary__item--ok .rhc-data-summary__value { color: var(--app-ok); }

.rhc-table-wrapper { overflow-x: auto; }
.rhc-table {
  inline-size: 100%; border-collapse: collapse;
  background: var(--app-surface); border: 1px solid var(--app-line);
}
.rhc-table th, .rhc-table td {
  text-align: start; padding: var(--app-space-sm) var(--app-space-md);
  border-block-end: 1px solid var(--app-line); font-size: 0.92rem;
}
.rhc-table th { color: var(--app-muted); font-weight: 600; }
.rhc-table tr:last-child td { border-block-end: none; }
.rhc-table .num { text-align: end; white-space: nowrap; }

.rhc-badge {
  display: inline-block; padding: 0.05rem 0.5rem; font-size: 0.75rem; font-weight: 700;
  border: 1px solid currentColor; border-radius: var(--rhc-border-radius-round, 999px);
}
.rhc-badge--error { color: var(--app-error); }
.rhc-badge--warning { color: var(--app-warning-text); background: var(--app-warning-bg); }
.rhc-badge--info { color: var(--app-info); }
.rhc-badge--ok { color: var(--app-ok); }

.rhc-accordion__section {
  background: var(--app-surface); border: 1px solid var(--app-line);
  padding: var(--app-space-md); margin-block-end: var(--app-space-sm);
}
.rhc-accordion__section summary { cursor: pointer; font-weight: 600; }
.rhc-unordered-list { margin-block: var(--app-space-md) 0; padding-inline-start: 1.15rem; }
.rhc-unordered-list li { margin-block-end: 0.35rem; font-size: 0.92rem; }
.rhc-paragraph--rule {
  color: var(--app-muted); font-size: 0.9rem; margin-block: var(--app-space-sm) 0;
}
.rhc-empty { color: var(--app-muted); font-style: italic; }

.rhc-page-footer {
  border-block-start: 1px solid var(--app-line);
  color: var(--app-muted); font-size: 0.82rem;
}
.rhc-page-footer__inner { padding-block: var(--app-space-md); }
.rhc-link { color: inherit; }

.rhc-button {
  display: inline-block; flex: none;
  padding: 0.55rem 1rem; font-weight: 600; font-size: 0.92rem;
  color: var(--app-brand-text); background: transparent;
  border: 1.5px solid var(--app-brand-text);
  border-radius: var(--rhc-border-radius-none, 0);
  text-decoration: none; white-space: nowrap;
}
.rhc-button:hover { background: var(--app-brand-text); color: var(--app-brand); }
"""
