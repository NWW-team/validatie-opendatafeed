# Peiling 14-09-2026 — wat de feed op dit moment laat zien

Volledige ronde over alle landen, met `BQ-BO`, `BQ-SA` en `BQ-SE` als
toegestane landcodes en Vaticaanstad buiten beschouwing (zie hieronder).
Bedoeld als nulmeting: hiermee is zichtbaar wat "normaal" is, zodat een nieuwe
afwijking opvalt. De ronde is die middag en avond twee keer gedraaid met
identieke uitkomsten.

## Uitkomst

**0 blokkerende bevindingen, 18 waarschuwingen en 127 informatieve
meldingen** over 226 getoetste landen.

## Vaticaanstad: uitgesloten, en waarom

De feed bevat 227 landen en 226 reisadviezen. Het verschil is Heilige Stoel /
Vaticaanstad, waar geen reisadvies meer van gemaakt wordt. Opvallend daarbij:
het landrecord verwijst wél naar een reisadvies dat niet bestaat.

```
200  /infotypes/countries/vaticaanstad                 het land bestaat
200  /infotypes/countries/vaticaanstad/nl-representation
404  /infotypes/countries/vat/traveladvice             het reisadvies niet
```

Het veld `travelAdvice` in het landrecord wijst naar die 404. Een afnemer die
dat veld volgt — wat de bedoeling is — loopt dus tegen een dode link aan. Het
land is met `--negeer-land vaticaanstad` uit de toetsing gehaald, maar het
schoonmaken van die pointer in het CMS blijft een aanbeveling.

## Systemisch (uit de waarschuwingen)

- **Contactvelden ontbreken feedbreed** (F07). Telefoonnummer, e-mailadres en
  noodnummer zijn bij alle 253 vertegenwoordigingen leeg. Dat is geen
  redactionele omissie per post, maar een gat in de feed zelf: een afnemer kan
  deze gegevens nergens vandaan halen.
- **Vijf posten zonder adres** (L18): Kaboel, Tripoli, St. Petersburg,
  Khartoem en Damascus — allemaal gesloten of opgeschort. De 109 andere
  vertegenwoordigingen zonder eigen adresregels zijn verwijzingen naar een
  post in een ander land; hun adres staat daar wél, en de validator legt die
  koppeling via het gedeelde `id`.
- **Twee datums lopen uiteen** (L12, informatief): bij 78 landen wijkt het technische veld
  `lastmodified` af van de getoonde "Laatst gewijzigd op". Een afnemer die op
  `lastmodified` sorteert of cachet, laat dus een andere datum zien dan de
  website.
- **Negen landen zonder vertegenwoordiging** (L17), waarvan Antarctica en
  Faeröer met een HTTP 404 op het endpoint en Aruba, Bonaire en Curaçao zonder
  records.

## De pushdatum (`issued`)

`issued` is het moment waarop een advies actief is gepusht: de Reisapp leidt er
een notificatie uit af, de informatieservice een bericht. Het veld staat bij
alle 226 adviezen, is overal leesbaar en nergens toekomstig — de keten waar die
melding uit komt, is dus intact.

Wat opvalt:

- **122 van de 226 adviezen delen één pushmoment** (07-08-2023 20:26 UTC).
  Dat is een bulkactie; voor die landen is er sindsdien geen notificatie meer
  uitgegaan. Op zichzelf geen defect — een stabiel advies hoeft niet gepusht te
  worden — maar het verklaart waarom de meeste pushdatums oud zijn.
- **48 adviezen zijn de afgelopen 30 dagen gewijzigd zonder push** (L23). Bij
  een kleine correctie is dat een bewuste keuze; bij een inhoudelijke wijziging
  betekent het dat reizigers geen melding hebben gekregen. Deze lijst is het
  aanknopingspunt voor de redactie.
- **Antarctica** heeft een pushdatum (07-08-2023) die vóór de eerste publicatie
  ligt (24-04-2024) — één van beide datums klopt niet.

De regel die de getoonde wijzigingsdatum met `lastmodified` vergelijkt (L12)
staat sinds deze peiling op informatief. Uit de data blijkt dat die twee
legitiem uiteenlopen: `lastmodified` verspringt bij elke bewerking, de getoonde
datum alleen bij een inhoudelijke wijziging. Van de 226 adviezen komt de
getoonde datum bij 148 overeen met `lastmodified`, bij 20 met `issued`, en bij
70 met geen van beide. Als waarschuwing leverde dat 78 meldingen op die geen
actie vroegen.

## Wat wél volledig op orde is

Alle getoetste landen hebben een geldige ISO-code die overeenkomt met het
reisadvies, een titel, een gevulde introductie, inhoudelijke tekstblokken
zonder gaten, een volledig beschreven kaart, een leesbare en niet-toekomstige
wijzigingsdatum, een recente geldigheidsdatum en een correcte canonical-URL
naar de website. Met `--check-files` en `--check-website` op een steekproef
waren ook de kaartbestanden op te halen en kwamen de datums op de website
overeen met de feed.

## Aandachtspunten bij het lezen

- `BQ-BO`, `BQ-SA` en `BQ-SE` (Bonaire, Saba, Sint Eustatius) zijn geen
  ISO 3166-1 alpha-3 codes. Ze zijn expliciet toegestaan; laat je die vlaggen
  weg, dan meldt L02 ze als fout.
- De aantallen hierboven komen uit één peiling. Bewaar `rapport/snapshot.json`
  als je een bevinding later precies wilt kunnen reconstrueren.
