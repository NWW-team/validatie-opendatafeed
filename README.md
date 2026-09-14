# Validatie opendatafeed reisadviezen

Toetst de [opendatafeed van Nederland Wereldwijd](https://www.nederlandwereldwijd.nl/open-data)
aan een vaste set volledigheids- en kwaliteitsregels, en maakt de uitkomst
zichtbaar in één rapport.

Waarom: als een reisadvies niet goed toont in de Reisapp, op de website of in de
informatieservice, ontstaat er discussie of het misgaat in het CMS, in de
opendatafeed of bij het afnemende systeem. Dit gereedschap beantwoordt de
middelste vraag met bewijs, zonder koppeling met de brondata in het CMS. Zie
[STRATEGY.md](STRATEGY.md) voor de achterliggende keuzes.

## Snel starten

```bash
pip install -e .

feedvalidator                      # alle landen toetsen, rapport in ./rapport
feedvalidator --limit 5            # snelle proef op vijf landen
feedvalidator regels               # de regelcatalogus tonen
open rapport/index.html            # het rapport bekijken
```

Een volledige ronde (227 landen, ruim 700 verzoeken) duurt ongeveer een halve
minuut.

## Wat er gecontroleerd wordt

24 regels, verdeeld over de feed als geheel (`F…`) en elk land afzonderlijk
(`L…`). `feedvalidator regels` toont ze met uitleg; kort samengevat:

| Onderwerp | Regels |
| --- | --- |
| Bereikbaarheid en dekking | alle endpoints antwoorden, elk land heeft een reisadvies, geen weesadviezen, unieke ISO-codes en landsleutels, hulp-bij-nood aanwezig |
| Inhoud van het reisadvies | titel, introductie, inhoudscategorieën met gevulde tekstblokken |
| Kaarten | kaart aanwezig, volledig beschreven, en met `--check-files` ook daadwerkelijk op te halen |
| Datums | leesbare wijzigingsdatum, technische en getoonde datum gelijk, niet in de toekomst, geldigheidsdatum recent |
| Ambassades en consulaten | vertegenwoordiging aanwezig, adres gevuld, contactvelden komen door de feed heen |
| Vergelijking met de website | met `--check-website`: toont nederlandwereldwijd.nl dezelfde wijzigingsdatum als de feed |

Regels met de zwaarte **Fout** zijn blokkerend (exitcode 1);
**Waarschuwing** en **Info** niet. Met `--fail-on warning` of `--fail-on never`
verschuif je die grens.

## Uitvoer

Elke ronde schrijft drie bestanden in `--output-dir` (standaard `rapport/`):

- `index.html` — het rapport voor de product owner, in de vormgeving van de
  Rijkshuisstijl Community;
- `rapport.json` — dezelfde uitkomst machineleesbaar, per regel en per bevinding;
- `rapport.md` — een samenvatting, onder meer voor het GitHub Actions-overzicht.

Met `--save-snapshot pad.json` bewaar je de ruwe feed van dat moment. Met
`--from-snapshot pad.json` draai je de regels daar later opnieuw overheen —
handig om een peiling te reconstrueren of een regel bij te stellen zonder de
feed te belasten.

## Veelgebruikte opties

| Optie | Doet |
| --- | --- |
| `--limit N` | alleen de eerste N landen |
| `--workers N` | aantal parallelle verzoeken (standaard 8) |
| `--check-files` | elk kaartbestand daadwerkelijk ophalen |
| `--check-website` | wijzigingsdatum vergelijken met nederlandwereldwijd.nl |
| `--allow-isocode CODE` | een landcode accepteren die van ISO 3166-1 afwijkt (herhaalbaar) |
| `--geldigheid-max-dagen N` | drempel voor "Nog steeds geldig op" (standaard 180) |
| `--fail-on error\|warning\|never` | wanneer de exitcode 1 wordt |
| `--no-theme-css` | geen extern stylesheet laden in het HTML-rapport |

## Automatisering

`.github/workflows/validatie.yml` draait elke werkdagochtend: tests, daarna een
volledige validatie. De samenvatting komt in het run-overzicht, het volledige
rapport blijft 90 dagen als artefact beschikbaar, en de run faalt bij
blokkerende bevindingen. De workflow is ook handmatig te starten, met
`--check-files` en `--check-website` als aan te vinken opties.

`.github/workflows/publiceer-rapport.yml` publiceert het HTML-rapport op GitHub
Pages, zodat er een vaste URL is om naar te verwijzen. Zet Pages in de
repo-instellingen op "GitHub Actions" voordat die workflow voor het eerst
draait.

## Over de feed

- Basis-URL: `https://opendata.nederlandwereldwijd.nl/v2/sources/nederlandwereldwijd`
  (v1 is uitgefaseerd en antwoordt met HTTP 410).
- Geen API-sleutel nodig; licentie CC0 1.0.
- Drie eigenaardigheden die deze validator afvangt:
  1. de standaarduitvoer is XML — JSON krijg je met `?output=json`, de
     `Accept`-header wordt genegeerd;
  2. `rows` wordt afgekapt op 200, dus lijsten vragen om paginering met
     `offset`;
  3. de Azure Application Gateway blokkeert een aantal standaard user agents
     (waaronder `python-requests/x.y`) met HTTP 403 — stuur altijd een eigen
     user agent mee.

## Vormgeving

Het HTML-rapport gebruikt de opmaak en klassenamen van de
[Rijkshuisstijl Community](https://github.com/nl-design-system/rijkshuisstijl-community):
`rhc-theme`, `rhc-heading` / `nl-heading--level-*`, `rhc-alert`, en `--rhc-*`
design tokens.

De huisstijlbestanden zelf worden niet meegeleverd — op het logo, de
lettertypes en de kleuren rusten auteursrechten, en gebruik is voorbehouden aan
de Rijksoverheid en aan partijen die voor de Rijksoverheid werken. Het rapport
verwijst standaard naar het gepubliceerde tokenpakket (aan te passen met
`--theme-css`, uit te zetten met `--no-theme-css`) en valt zonder dat pakket
terug op een kleine set tokenwaarden, zodat een rapport in een CI-artefact ook
zonder netwerk leesbaar blijft.

## Ontwikkelen

```bash
pip install -e ".[dev]"
pytest -q
ruff check src tests
```

De tests draaien zonder netwerk: `tests/conftest.py` bouwt realistische
feedrecords en elke regel heeft een geval dat slaagt en een geval dat faalt.
