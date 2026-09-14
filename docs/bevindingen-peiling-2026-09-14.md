# Peiling 14-09-2026 — wat de feed op dit moment laat zien

Volledige ronde over alle landen, met `BQ-BO`, `BQ-SA` en `BQ-SE` als
toegestane landcodes en Vaticaanstad buiten beschouwing (zie hieronder).
Bedoeld als nulmeting: hiermee is zichtbaar wat "normaal" is, zodat een nieuwe
afwijking opvalt. De ronde is die middag en avond twee keer gedraaid met
identieke uitkomsten.

## Uitkomst

**0 blokkerende bevindingen, 13 waarschuwingen en 52 informatieve
meldingen** over 226 getoetste landen.

## Let op: de feed knijpt af

De gateway antwoordt met HTTP 429 als de verzoeken te snel gaan. Een eerdere
ronde vanaf een GitHub-runner liep daar tegenaan en rapporteerde daardoor 44
"reisadviezen niet op te halen", 49 landen zonder vertegenwoordiging en 208 in
plaats van 253 vertegenwoordigingen. Dat waren geen feedproblemen maar te
snelle verzoeken.

Sindsdien blijft de validator onder een instelbaar tempo (standaard zes
verzoeken per seconde, vier tegelijk) en volgt hij `Retry-After`. Een volledige
ronde duurt daarmee ongeveer twee minuten. Wordt er tóch afgeknepen, dan meldt
regel F10 dat het rapport onvolledig is en zwijgen L01 en L17 erover — een
afgeknepen verzoek is geen ontbrekend reisadvies.

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
- **Vijf gesloten posten zonder adres**: Kaboel, Tripoli, St. Petersburg,
  Khartoem en Damascus. Deze posten zijn gesloten en worden door geen andere
  post waargenomen; ze staan daarom met `--gesloten-post` als bekend gemerkt
  en leveren geen waarschuwing meer op. Regel F12 meldt het zodra die aanname
  niet meer klopt. Van de 114
  vertegenwoordigingen zonder eigen adresregels wijzen er 109 met hun
  `dataurl` naar een post in een ánder land; daar staat het adres, en die
  verwijzing telt dus als een adres. Alleen deze vijf verwijzen naar zichzelf.
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
- **50 adviezen hebben de afgelopen 30 dagen beweging zonder push** (L12):
  48 zichtbaar gewijzigd zonder dat er een push op volgde, en 2 stil gewijzigd
  — bewerkt ná de datum die de lezer ziet. Bij een kleine correctie is dat een
  bewuste keuze; bij een inhoudelijke wijziging betekent het dat reizigers geen
  melding hebben gekregen. Deze lijst is het aanknopingspunt voor de redactie.
- **Antarctica** heeft een pushdatum (07-08-2023) die vóór de eerste publicatie
  ligt (24-04-2024) — één van beide datums klopt niet.

L12 zet de drie datums naast elkaar met een duiding erachter, in plaats van
twee losse regels die elk een stukje van het beeld gaven. Over alle 226
adviezen verdeelt dat zich zo: bij 12 is de push de laatste beweging, bij 78
is `lastmodified` het laatst (stil gewijzigd) en bij 136 de getoonde datum
(gewijzigd, niet gepusht). Alleen wat binnen het venster van 30 dagen valt
wordt gemeld — 50 adviezen — want oudere beweging vraagt geen actie meer.

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
