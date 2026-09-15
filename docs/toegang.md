# Toegang: inloggen met Supabase Auth

De bevindingen zijn afgeschermd voor een vaste lijst accounts. Dit document
beschrijft waar die afscherming zit, wat je zelf in Supabase moet klikken, en
hoe je controleert dat het klopt.

## Wat wel en niet afgeschermd is

| | Openbaar | Afgeschermd |
| --- | --- | --- |
| `web/index.html`, `web/app.js`, `web/config.js` | ja | — |
| Project-URL en publishable key | ja, dat hoort zo | — |
| Rijen in `rapporten` en `bevindingen` | — | ja, door RLS |
| De allowlist zelf | — | ja, onleesbaar via de API |

De schil op GitHub Pages is een publiek bestand. Iedereen kan hem opvragen,
de broncode lezen en de knoppen vinden. Dat is geen lek: er staat niets in.
De afscherming zit in Postgres, bij het gegevensverzoek, en geldt daarom ook
voor een verzoek dat de pagina helemaal overslaat.

De toegangsregel is niet "is er een sessie?" maar:

```
ingelogd  ÉN  het e-mailadres staat in toegestane_gebruikers
```

Beide voorwaarden staan in de policy zelf (`db/0001_toegang.sql`). Vrije
registratie hoort daarnaast uit te staan in het dashboard (stap 3 hieronder),
maar dat is de tweede schil. Zou iemand tóch een account krijgen, dan levert
dat nog steeds geen rij op.

## Eenmalig instellen in Supabase

### 1. De tabellen en policies aanmaken — al gedaan

Dit schema staat al in het project `rckbrn's validatietool`, aangebracht als
migratie `toegang_allowlist_en_rls`. Je hoeft hier niets te klikken.

Voor een ander project, of om het opnieuw te doen:

1. Open het project in [supabase.com/dashboard](https://supabase.com/dashboard).
2. Klik links op **SQL Editor** en daarna op **New query**.
3. Plak de volledige inhoud van [`db/0001_toegang.sql`](../db/0001_toegang.sql).
4. Pas onderin het e-mailadres aan naar het testaccount dat toegang moet
   krijgen (standaard `toegestaan@example.org`).
5. Klik op **Run**. Het script is herhaalbaar: nog eens draaien doet geen kwaad.
6. Controleer via **Table Editor** dat `toegestane_gebruikers`, `rapporten` en
   `bevindingen` bestaan en dat er bij elke tabel *RLS enabled* staat.

### 2. Twee testaccounts aanmaken — nog te doen

1. Klik links op **Authentication** en dan op **Users**.
2. Klik op **Add user → Create new user**.
3. Vul `toegestaan@example.org` in met een wachtwoord naar keuze en zet
   **Auto Confirm User** aan. Dat maakt het account direct bruikbaar zonder
   bevestigingsmail, en het verandert niets aan je e-mailinstellingen.
4. Herhaal dit voor `buitenstaander@example.org`. Dit account zet je **niet**
   op de allowlist — het bestaat om te bewijzen dat inloggen alleen niet genoeg
   is.
5. Bewaar de wachtwoorden in je wachtwoordbeheerder, niet in deze repo.

### 3. Vrije registratie uitzetten — nog te doen

1. Ga naar **Authentication → Sign In / Providers** (in oudere projecten:
   **Providers**) en open **Email**.
2. Zet **Allow new users to sign up** uit en klik op **Save**.

Bedient dit Supabase-project ook iets anders, controleer dan eerst of daar
geen zelfregistratie nodig is.

### 4. De publieke sleutels in de frontend zetten — al gedaan

[`web/config.js`](../web/config.js) wijst naar
`https://tkfasdijhdthywxorqwa.supabase.co` met de publishable key van dat
project. Voor een ander project: **Project Settings → API Keys** (in oudere
projecten: **API**), kopieer de **Project URL** en de **publishable key** (daar
`anon` `public` geheten) en zet ze in dat bestand.

De **service_role**- of **secret**-sleutel hoort daar nooit. Die negeert RLS
en geeft toegang tot alles. Hij is alleen nodig als de CI straks rondes
wegschrijft, en staat dan in GitHub onder *Settings → Secrets and variables →
Actions*.

## Wat er in de database is nagemeten

De policies zijn getoetst door de rollen en JWT-claims na te bootsen zoals
PostgREST ze zet. Dit is gemeten, niet aangenomen:

| Wie | `is_toegestaan()` | `bevindingen` | `rapporten` | `toegestane_gebruikers` |
| --- | --- | --- | --- | --- |
| `anon`, geen sessie | n.v.t. (mag de functie niet aanroepen) | 0 | 0 | 0 |
| `authenticated`, `toegestaan@example.org` | `true` | 4 | 1 | 0 |
| `authenticated`, `buitenstaander@example.org` | `false` | 0 | 0 | 0 |

De allowlist is dus voor niemand leesbaar, ook niet voor wie er zelf op staat.

Schrijven is ook geprobeerd, als het toegestane account:

- `insert` → geweigerd: *new row violates row-level security policy for table
  "bevindingen"*.
- `delete` → geen foutmelding, maar nul rijen geraakt: zonder policy ziet de
  opdracht geen enkele rij om te verwijderen.

En een paar randgevallen van het token:

| Token | Op de lijst | Bevindingen |
| --- | --- | --- |
| `TOEGESTAAN@Example.ORG` — zelfde adres, andere schrijfwijze | ja | 4 |
| geldige sessie zonder `email`-claim | nee | 0 |
| niet-toegestaan adres, met `"is_toegestaan": true` en `"admin": true` erin verzonnen | nee | 0 |
| `toegestaan@example.org.evil.test` — lijkt op het toegestane adres | nee | 0 |

Verzonnen claims halen dus niets uit: de policy kijkt niet naar wat het token
bewéért, maar zoekt het adres op in de allowlist.

Twee dingen die deze meting bevestigt en die makkelijk te verwarren zijn:

- `anon` mag `is_toegestaan()` niet eens aanroepen: *permission denied for
  function is_toegestaan*.
- `anon` en `authenticated` hebben allebei gewoon een `select`-recht op de drie
  tabellen. Wat ze tegenhoudt is dus RLS, niet een ontbrekend recht. Dat is
  precies de bedoeling: een recht kan iemand later per ongeluk uitdelen, de
  policy blijft dan staan.

## Testen in de browser — nog te doen

Dit deel is nog niet gedaan, en kan ook niet vanuit de ontwikkelomgeving: die
mag `*.supabase.co` en `*.github.io` niet benaderen, en de twee testaccounts
bestaan nog niet. Er is dus nog geen enkele echte inlogsessie geweest.

De schil staat na publicatie op `/toegang/` naast het rapport. Doorloop deze
zes gevallen; de verwachte uitkomst staat erbij.

| # | Wat je doet | Wat er hoort te gebeuren |
| --- | --- | --- |
| 1 | De pagina openen zonder in te loggen | Alleen het inlogformulier. Geen bevindingen in beeld en geen bevindingen in de netwerkverzoeken. |
| 2 | Inloggen als `toegestaan@example.org` | De tabel met bevindingen verschijnt. |
| 3 | Inloggen als `buitenstaander@example.org` | "Geen toegang". Het account is ingelogd, de database geeft niets vrij. |
| 4 | De directe URL van de pagina openen in een nieuw tabblad | Hetzelfde als geval 1: het bestand is openbaar, de inhoud niet. |
| 5 | Het directe gegevensverzoek openen (de URL onderaan de pagina) | `[]` — een lege lijst. Dit is het verzoek dat de pagina overslaat. |
| 6 | Uitloggen en daarna vernieuwen, terug, of de URL opnieuw openen | Terug bij het inlogformulier; geen oude gegevens in beeld. |

Bij geval 5 helpt het om in de ontwikkelaarsconsole (F12 → *Network*) mee te
kijken: bij geval 1 hoort er helemaal geen verzoek naar `/rest/v1/bevindingen`
te gaan, en bij geval 3 hoort dat verzoek `[]` terug te geven — niet een
gefilterde lijst en niet een foutmelding die iets prijsgeeft.

## Meldingen van de Supabase-linter

Drie meldingen staan open; twee zijn bedoeld, één is niet van ons:

- *RLS Enabled No Policy* op `toegestane_gebruikers` — **bedoeld**. Geen policy
  is hier de policy: niemand leest de lijst via de API.
- *Signed-In Users Can Execute SECURITY DEFINER Function* voor
  `is_toegestaan()` — **bedoeld**. De functie vertelt de aanroeper alleen iets
  over zichzelf, en de schil gebruikt dat voor het verschil tussen "niets
  gevonden" en "jij mag dit niet zien".
- Dezelfde melding voor `public.rls_auto_enable()` — **stond er al**. Dat is een
  event-triggerfunctie die RLS aanzet op nieuwe tabellen in `public`. Aanroepen
  via de API lukt, maar doet niets: buiten een event trigger levert de lus geen
  commando's op. Wil je de melding kwijt, dan kan
  `revoke execute on function public.rls_auto_enable() from anon, authenticated;`
  — dat raakt de werking van de event trigger niet.

## Wat hierna nog moet

- **De rondes wegschrijven.** Nu staan er demorijen in de tabellen. De stap die
  `rapport.json` na elke CI-ronde naar Supabase schrijft, bestaat nog niet.
- **Het publieke rapport.** `index.html` met alle bevindingen staat nog
  onveranderd op GitHub Pages. Zolang dat zo is, is de inhoud openbaar en is
  de afscherming hiernaast een oefening. Die keuze staat nog open.
