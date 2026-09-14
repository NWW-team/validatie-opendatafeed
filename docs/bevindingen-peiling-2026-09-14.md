# Peiling 14-09-2026 — wat de feed op dit moment laat zien

Eerste volledige ronde over alle 227 landen, met `BQ-BO`, `BQ-SA` en `BQ-SE`
als toegestane landcodes. Bedoeld als nulmeting: hiermee is zichtbaar wat
"normaal" is, zodat een nieuwe afwijking opvalt.

## Blokkerend (2 bevindingen)

- **Heilige Stoel / Vaticaanstad** staat in `/infotypes/countries`, maar heeft
  geen reisadvies: de index kent het land niet (F03) en het detail-endpoint
  antwoordt met HTTP 404 (L01). Dit verklaart het verschil tussen de 227 landen
  en de 226 reisadviezen in de feed.

## Systemisch (uit de waarschuwingen)

- **Contactvelden ontbreken feedbreed** (F07). Telefoonnummer, e-mailadres en
  noodnummer zijn bij alle 253 vertegenwoordigingen leeg. Dat is geen
  redactionele omissie per post, maar een gat in de feed zelf: een afnemer kan
  deze gegevens nergens vandaan halen.
- **Adres ontbreekt bij de helft** (L18): 114 van de 227 landen hebben een
  vertegenwoordiging zonder adres — vaak een post in een buurland die het land
  mede bedient.
- **Twee datums lopen uiteen** (L12): bij 78 landen wijkt het technische veld
  `lastmodified` af van de getoonde "Laatst gewijzigd op". Een afnemer die op
  `lastmodified` sorteert of cachet, laat dus een andere datum zien dan de
  website.
- **Negen landen zonder vertegenwoordiging** (L17), waarvan Antarctica en
  Faeröer met een HTTP 404 op het endpoint en Aruba, Bonaire en Curaçao zonder
  records.

## Wat wél volledig op orde is

Alle 227 landen hebben een geldige ISO-code die overeenkomt met het reisadvies,
een titel, een gevulde introductie, inhoudelijke tekstblokken zonder gaten, een
volledig beschreven kaart, een leesbare en niet-toekomstige wijzigingsdatum,
een recente geldigheidsdatum en een correcte canonical-URL naar de website.

## Aandachtspunten bij het lezen

- `BQ-BO`, `BQ-SA` en `BQ-SE` (Bonaire, Saba, Sint Eustatius) zijn geen
  ISO 3166-1 alpha-3 codes. Ze zijn hier expliciet toegestaan; laat je de
  vlaggen weg, dan meldt L02 ze als fout.
- De aantallen hierboven komen uit één peiling. Bewaar `rapport/snapshot.json`
  als je een bevinding later precies wilt kunnen reconstrueren.
