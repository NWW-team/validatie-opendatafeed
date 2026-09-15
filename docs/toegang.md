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
4. Klik op **Run**. Het script is herhaalbaar: nog eens draaien doet geen kwaad.
5. Zet daarna de adressen die toegang krijgen in `toegestane_gebruikers`. Die
   staan bewust niet in het script: de repo is openbaar en een allowlist is een
   lijst met mensen.
6. Controleer via **Table Editor** dat `toegestane_gebruikers`, `rapporten` en
   `bevindingen` bestaan en dat er bij elke tabel *RLS enabled* staat.

### 2. Twee testaccounts aanmaken — al gedaan

Er staan twee bevestigde accounts met een wachtwoord in het project: één op de
allowlist, één er bewust naast. De adressen staan hier niet; ze staan in
**Authentication → Users** en in `toegestane_gebruikers`.

Voor een volgend account:

1. Klik links op **Authentication** en dan op **Users**.
2. Klik op **Add user → Create new user**.
3. Vul het adres in met een wachtwoord naar keuze en zet **Auto Confirm User**
   aan. Dat maakt het account direct bruikbaar zonder bevestigingsmail, en het
   verandert niets aan je e-mailinstellingen.
4. Wil het account ook echt iets kunnen zien, zet het adres dan in
   `toegestane_gebruikers`. Zonder die regel kan het inloggen en verder niets —
   en dat is een prima manier om de afscherming te blijven controleren.
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
| het toegestane account | `true` | 4 | 1 | 0 |
| het niet-toegestane account | `false` | 0 | 0 | 0 |

De onderste twee rijen zijn gemeten met de `sub` en het e-mailadres van de
accounts die echt in `auth.users` staan, in de vorm waarin PostgREST ze in het
token zet.

De allowlist is dus voor niemand leesbaar, ook niet voor wie er zelf op staat.

Schrijven is ook geprobeerd, als het toegestane account:

- `insert` → geweigerd: *new row violates row-level security policy for table
  "bevindingen"*.
- `delete` → geen foutmelding, maar nul rijen geraakt: zonder policy ziet de
  opdracht geen enkele rij om te verwijderen.

En een paar randgevallen van het token:

| Token | Op de lijst | Bevindingen |
| --- | --- | --- |
| het toegestane adres, maar met hoofdletters geschreven | ja | 4 |
| geldige sessie zonder `email`-claim | nee | 0 |
| een niet-toegestaan adres, met `"is_toegestaan": true` en `"admin": true` erin verzonnen | nee | 0 |
| een adres dat op het toegestane lijkt, met een extra domein erachter | nee | 0 |

Verzonnen claims halen dus niets uit: de policy kijkt niet naar wat het token
bewéért, maar zoekt het adres op in de allowlist.

Twee dingen die deze meting bevestigt en die makkelijk te verwarren zijn:

- `anon` mag `is_toegestaan()` niet eens aanroepen: *permission denied for
  function is_toegestaan*.
- `anon` en `authenticated` hebben allebei gewoon een `select`-recht op de drie
  tabellen. Wat ze tegenhoudt is dus RLS, niet een ontbrekend recht. Dat is
  precies de bedoeling: een recht kan iemand later per ongeluk uitdelen, de
  policy blijft dan staan.

## Testen in de browser

De schil staat op `/toegang/` naast het rapport. Stand van 15-09-2026:

| # | Wat je doet | Wat er hoort te gebeuren | Gedaan |
| --- | --- | --- | --- |
| 1 | De pagina openen zonder in te loggen | Alleen het inlogformulier. Geen bevindingen in beeld en geen bevindingen in de netwerkverzoeken. | nog niet |
| 2 | Inloggen met het toegestane account | De tabel met bevindingen verschijnt. | ja, vier bevindingen |
| 3 | Inloggen met het niet-toegestane account | "Geen toegang". Het account is ingelogd, de database geeft niets vrij. | ja |
| 4 | De directe URL van de pagina openen in een nieuw tabblad | Hetzelfde als geval 1: het bestand is openbaar, de inhoud niet. | nog niet |
| 5 | Het directe gegevensverzoek openen (de URL onderaan de pagina) | `[]` — een lege lijst. Dit is het verzoek dat de pagina overslaat. | nog niet |
| 6 | Uitloggen en daarna vernieuwen, terug, of de URL opnieuw openen | Terug bij het inlogformulier; geen oude gegevens in beeld. | nog niet |

Geval 2 en 3 zijn ook in de database terug te zien: beide accounts hebben een
`last_sign_in_at`, dus er zijn echte sessies geweest. Daarmee is bewezen wat
uit de policytoets alleen niet volgt — dat `signInWithPassword` werkt met de
publishable key, dat het token wordt meegestuurd, en dat hetzelfde verschil
tussen "ingelogd" en "toegestaan" dat in SQL is gemeten ook in de browser
uitkomt.

Wat nog open staat, is het uitgelogde pad: geval 1, 4, 5 en 6.

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
