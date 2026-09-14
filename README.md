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

Een volledige ronde is ruim 700 verzoeken over 227 landen. Die gaan op tempo
(standaard zes per seconde, vier tegelijk) omdat de feed anders afknijpt, dus
reken op twee tot drie minuten.

## Wat er gecontroleerd wordt

31 regels, verdeeld over de feed als geheel (`F…`) en elk land afzonderlijk
(`L…`). `feedvalidator regels` toont ze met uitleg; kort samengevat:

| Onderwerp | Regels |
| --- | --- |
| Bereikbaarheid en dekking | alle endpoints antwoorden, elk land heeft een reisadvies, geen weesadviezen, unieke ISO-codes en landsleutels, hulp-bij-nood aanwezig |
| Inhoud van het reisadvies | titel, introductie, inhoudscategorieën met gevulde tekstblokken |
| Kaarten | kaart aanwezig, volledig beschreven, en met `--check-files` ook daadwerkelijk op te halen |
| Datums | leesbare wijzigingsdatum, technische en getoonde datum gelijk, niet in de toekomst, geldigheidsdatum recent |
| Pushdatum (`issued`) | aanwezig en leesbaar, niet in de toekomst, niet vóór de eerste publicatie, en een recente wijziging is ook gepusht |
| Ambassades en consulaten | vertegenwoordiging aanwezig, adres ergens in de feed te vinden, contactvelden komen door de feed heen |
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

Landen die met `--negeer-land` zijn uitgesloten, worden niet getoetst en tellen
niet mee in de aantallen, maar staan wél met naam in het rapport — zo raakt
niemand ze stilletjes kwijt. Verdwijnt zo'n land later uit de feed, dan meldt
regel F08 dat de vlag weg kan, zodat de instelling meegroeit met de feed.

Met `--save-snapshot pad.json` bewaar je de ruwe feed van dat moment. Met
`--from-snapshot pad.json` draai je de regels daar later opnieuw overheen —
handig om een peiling te reconstrueren of een regel bij te stellen zonder de
feed te belasten.

## Veelgebruikte opties

| Optie | Doet |
| --- | --- |
| `--limit N` | alleen de eerste N landen |
| `--workers N` | aantal parallelle verzoeken (standaard 4) |
| `--verzoeken-per-seconde N` | bovengrens aan het tempo (standaard 6) |
| `--check-files` | elk kaartbestand daadwerkelijk ophalen |
| `--check-website` | wijzigingsdatum vergelijken met nederlandwereldwijd.nl |
| `--allow-isocode CODE` | een landcode accepteren die van ISO 3166-1 afwijkt (herhaalbaar) |
| `--negeer-land SLEUTEL` | een land buiten beschouwing laten, bijvoorbeeld omdat er bewust geen reisadvies van is (herhaalbaar) |
| `--geldigheid-max-dagen N` | drempel voor "Nog steeds geldig op" (standaard 180) |
| `--push-venster-dagen N` | hoe ver terug een wijziging "recent" heet bij het toetsen op een push (standaard 30) |
| `--fail-on error\|warning\|never` | wanneer de exitcode 1 wordt |
| `--no-theme-css` | geen extern stylesheet laden in het HTML-rapport |

## Automatisering

`.github/workflows/validatie.yml` draait elke werkdagochtend: tests, daarna een
volledige validatie. De samenvatting komt in het run-overzicht, het volledige
rapport blijft 90 dagen als artefact beschikbaar, en de run faalt bij
blokkerende bevindingen. De workflow is ook handmatig te starten, met
`--check-files` en `--check-website` als aan te vinken opties.

Op een pull request draait dezelfde validatie, maar houden bevindingen over de
feed de merge niet tegen: daar gaat het om de code, en een ontbrekend
reisadvies zegt niets over de wijziging die ter beoordeling ligt. Falen de
tests of de lint, dan wordt de PR uiteraard wel rood.

`.github/workflows/publiceer-rapport.yml` publiceert het HTML-rapport op GitHub
Pages, zodat er een vaste URL is om naar te verwijzen: na elke merge naar
`main`, elke werkdag om 07:45 UTC, en handmatig via *Run workflow*.

Zet Pages in de repo-instellingen onder *Settings → Pages → Source* op
**GitHub Actions** voordat die workflow voor het eerst draait — met de
instelling "Deploy from a branch" publiceert GitHub de README in plaats van het
rapport. Staat het goed, dan verdwijnt de automatische run
`pages build and deployment` uit het Actions-overzicht; zie je die na een push
nog steeds, dan staat de bron nog op de branch.

## De drie datums in een reisadvies

Ze lijken op elkaar en betekenen iets anders. Door elkaar halen is de snelste
weg naar een verkeerde conclusie:

| Veld | Wat het is | Wie erop stuurt |
| --- | --- | --- |
| `modificationdate` | de getoonde tekst "Laatst gewijzigd op … \| Nog steeds geldig op …" | de lezer op de website en in de Reisapp |
| `lastmodified` | technische timestamp van élke bewerking, ook een typefout | caches en sorteringen bij afnemers |
| `issued` | het moment waarop het advies actief is gepusht | de Reisapp (notificatie) en de informatieservice (bericht) |

Ze lopen in de praktijk uiteen, en dat mag: een correctie verspringt wel
`lastmodified` maar niet de getoonde datum, en verdient geen notificatie. Om
die reden meldt L12 alleen informatief dat de technische en de getoonde datum
verschillen. L23 kijkt naar het geval dat er wél toe doet: een wijziging van
de afgelopen `--push-venster-dagen` waar geen push op volgde.

## Posten die een ander land bedienen

Niet elk land heeft een eigen ambassade. Amerikaans-Samoa wordt bijvoorbeeld
bediend vanuit Wellington. In de feed staat onder Amerikaans-Samoa dan een
vertegenwoordiging met hetzelfde `id` als die van Nieuw-Zeeland en met een
`dataurl` die daarheen wijst, maar zonder adresregels — het adres staat bij
Nieuw-Zeeland.

Die link ís het adres — het staat er alleen achter. De validator leest het
land uit de `dataurl`: wijst die naar een ánder land dan het landrecord zelf,
dan is het een verwijzing en telt de post als voorzien van een adres. Dat
werkt ook als dat andere land buiten de ronde viel.

L18 meldt daarom alleen een post die naar zichzelf verwijst en tóch geen
adresregels heeft. In de peiling zijn dat er vijf: Kaboel, Tripoli,
St. Petersburg, Khartoem en Damascus — allemaal gesloten of opgeschort.

## Over de feed

- Basis-URL: `https://opendata.nederlandwereldwijd.nl/v2/sources/nederlandwereldwijd`
  (v1 is uitgefaseerd en antwoordt met HTTP 410).
- Geen API-sleutel nodig; licentie CC0 1.0.
- Vier eigenaardigheden die deze validator afvangt:
  1. de standaarduitvoer is XML — JSON krijg je met `?output=json`, de
     `Accept`-header wordt genegeerd;
  2. `rows` wordt afgekapt op 200, dus lijsten vragen om paginering met
     `offset`;
  3. de Azure Application Gateway blokkeert een aantal standaard user agents
     (waaronder `python-requests/x.y`) met HTTP 403 — stuur altijd een eigen
     user agent mee;
  4. diezelfde gateway knijpt af met HTTP 429 als de verzoeken te snel gaan.
     De validator blijft daarom onder `--verzoeken-per-seconde` en volgt
     `Retry-After`. Gebeurt het tóch, dan meldt regel F10 dat het rapport
     onvolledig is — een afgeknepen verzoek is geen ontbrekend reisadvies, en
     L01 en L17 zwijgen er dan over.

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
