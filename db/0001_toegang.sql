-- Toegang tot de afgeschermde rapportgegevens.
--
-- Plak dit in de SQL-editor van Supabase (zie docs/toegang.md voor het
-- klikpad). Het script is herhaalbaar: opnieuw draaien doet geen kwaad.
--
-- Het uitgangspunt: de regel staat hier, in de database, en niet in de
-- browser. Een pagina kan een knop verbergen; alleen een policy kan een
-- verzoek weigeren.

-- 1. Wie mag erbij --------------------------------------------------------

create table if not exists public.toegestane_gebruikers (
    email         text primary key check (email = lower(email)),
    notitie       text,
    toegevoegd_op timestamptz not null default now()
);

comment on table public.toegestane_gebruikers is
    'Vooraf toegestane accounts. Alleen te beheren vanuit het Supabase-dashboard '
    'of met de service-role key; via de API is deze tabel onleesbaar.';

alter table public.toegestane_gebruikers enable row level security;

-- Bewust géén policy op deze tabel. Zonder policy weigert RLS alles, dus ook
-- een ingelogde buitenstaander kan de lijst met e-mailadressen niet uitlezen.

-- 2. De toets ------------------------------------------------------------

create or replace function public.is_toegestaan()
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
    select exists (
        select 1
        from public.toegestane_gebruikers t
        where t.email = lower(auth.jwt() ->> 'email')
    );
$$;

comment on function public.is_toegestaan() is
    'Waar als de ingelogde gebruiker op de allowlist staat. security definer, '
    'omdat de allowlist zelf voor niemand leesbaar is.';

revoke execute on function public.is_toegestaan() from public, anon;
grant execute on function public.is_toegestaan() to authenticated;

-- 3. Wat er beschermd wordt ----------------------------------------------

create table if not exists public.rapporten (
    id                 bigint generated always as identity primary key,
    gegenereerd_op     timestamptz not null,
    base_url           text not null,
    samenvatting       jsonb not null default '{}'::jsonb,
    -- Alles wat de afgeschermde weergave nodig heeft om het rapport verder
    -- af te maken: het resultaat per regel (voor de tabel), de landen en
    -- posten die buiten beschouwing zijn gelaten, en endpoints die niet
    -- antwoordden. De losse bevindingen staan apart, in `bevindingen`.
    regelresultaten    jsonb not null default '[]'::jsonb,
    buiten_beschouwing text[] not null default '{}',
    gesloten_posten    text[] not null default '{}',
    fetch_fouten       jsonb not null default '{}'::jsonb,
    aangemaakt_op      timestamptz not null default now()
);

-- Draaide dit script eerder al, dan bestond de tabel voordat deze vier
-- kolommen er waren; `add column if not exists` haalt hem alsnog bij.
alter table public.rapporten add column if not exists regelresultaten jsonb not null default '[]'::jsonb;
alter table public.rapporten add column if not exists buiten_beschouwing text[] not null default '{}';
alter table public.rapporten add column if not exists gesloten_posten text[] not null default '{}';
alter table public.rapporten add column if not exists fetch_fouten jsonb not null default '{}'::jsonb;

create table if not exists public.bevindingen (
    id          bigint generated always as identity primary key,
    rapport_id  bigint not null references public.rapporten (id) on delete cascade,
    regel_id    text not null,
    regel_titel text not null,
    zwaarte     text not null check (zwaarte in ('error', 'warning', 'info')),
    boodschap   text not null,
    land        text,
    isocode     text
);

create index if not exists bevindingen_rapport_idx on public.bevindingen (rapport_id);

alter table public.rapporten enable row level security;
alter table public.bevindingen enable row level security;

-- Lezen mag alleen wie is ingelogd én op de allowlist staat. Twee
-- voorwaarden, één policy: een geldige sessie is niet genoeg.
drop policy if exists "toegestane gebruikers lezen rapporten" on public.rapporten;
create policy "toegestane gebruikers lezen rapporten"
    on public.rapporten
    for select
    to authenticated
    using (public.is_toegestaan());

drop policy if exists "toegestane gebruikers lezen bevindingen" on public.bevindingen;
create policy "toegestane gebruikers lezen bevindingen"
    on public.bevindingen
    for select
    to authenticated
    using (public.is_toegestaan());

-- Geen insert-, update- of delete-policy. Schrijven kan daardoor alleen met
-- de service-role key, die in GitHub Actions staat en nooit in de frontend.

-- 4. Wie op de lijst komt -------------------------------------------------

-- Bewust geen adressen in dit bestand: de repo is openbaar en een allowlist
-- is een lijst met mensen. Ze horen in de database, niet in git.
--
-- Een adres toevoegen doe je in de SQL-editor, met de tabel-editor, of hier
-- met één regel die je niet commit:
--
--     insert into public.toegestane_gebruikers (email, notitie)
--     values ('iemand@voorbeeld.nl', 'waarom deze persoon toegang heeft')
--     on conflict (email) do nothing;
--
-- Het e-mailadres moet in kleine letters; de check-constraint houdt dat vast.
-- Een account dat niet op de lijst staat, kan gewoon inloggen en krijgt toch
-- geen rij te zien: dat is precies het verschil tussen "ingelogd" en
-- "toegestaan", en dat verschil is het hele punt.

-- 5. Wat demogegevens om op te testen ------------------------------------

-- Eén demoronde, zodat er iets te zien is voordat de CI rondes wegschrijft.
-- Draait dit script nog eens, dan gebeurt hier niets: de guard kijkt of er al
-- een rapport staat.
with nieuwe_ronde as (
    insert into public.rapporten (
        gegenereerd_op, base_url, samenvatting,
        regelresultaten, buiten_beschouwing, gesloten_posten
    )
    select
        timestamptz '2026-09-14 20:00:00+02',
        'https://opendata.nederlandwereldwijd.nl/v2/sources/nederlandwereldwijd',
        '{"demo": true, "errors": 0, "warnings": 2, "infos": 2}'::jsonb,
        '[
            {"regel_id": "L12", "regel_titel": "De drie datums naast elkaar",
             "beschrijving": "Demo: zet getoond, gewijzigd en gepusht naast elkaar.",
             "zwaarte": "warning", "gecontroleerd": 220, "in_orde": 219,
             "bevindingen_aantal": 1, "ok": false},
            {"regel_id": "L17", "regel_titel": "Vertegenwoordiging aanwezig",
             "beschrijving": "Demo: elke genoemde vertegenwoordiging moet als record bestaan.",
             "zwaarte": "warning", "gecontroleerd": 220, "in_orde": 219,
             "bevindingen_aantal": 1, "ok": false},
            {"regel_id": "L18", "regel_titel": "Adres ergens in de feed te vinden",
             "beschrijving": "Demo: elke post heeft een adres, tenzij gesloten.",
             "zwaarte": "info", "gecontroleerd": 220, "in_orde": 219,
             "bevindingen_aantal": 1, "ok": false},
            {"regel_id": "F11", "regel_titel": "Landen die vanuit een andere post worden bediend",
             "beschrijving": "Demo: informatief overzicht, geen fout.",
             "zwaarte": "info", "gecontroleerd": 1, "in_orde": 0,
             "bevindingen_aantal": 1, "ok": false}
        ]'::jsonb,
        array['Vaticaanstad (vaticaanstad)'],
        array['Ambassade Kaboel (ambassade-kaboel)']
    where not exists (select 1 from public.rapporten)
    returning id
)
insert into public.bevindingen (rapport_id, regel_id, regel_titel, zwaarte, boodschap, land, isocode)
select nieuwe_ronde.id, v.regel_id, v.regel_titel, v.zwaarte, v.boodschap, v.land, v.isocode
from nieuwe_ronde
cross join (values
    ('L12', 'De drie datums naast elkaar', 'warning',
     'Demo: gewijzigd, niet gepusht — de laatste push is 1129 dagen ouder.',
     'Australië', 'AUS'),
    ('L17', 'Vertegenwoordiging aanwezig', 'warning',
     'Demo: het reisadvies noemt een vertegenwoordiging in Oranjestad die als record ontbreekt.',
     'Aruba', 'ABW'),
    ('L18', 'Adres ergens in de feed te vinden', 'info',
     'Demo: post verwijst naar zichzelf en heeft geen adresregels; gemarkeerd als gesloten.',
     'Syrië', 'SYR'),
    ('F11', 'Landen die vanuit een andere post worden bediend', 'info',
     'Demo: 14 landen worden bediend vanuit een post in een ander land.',
     null, null)
) as v (regel_id, regel_titel, zwaarte, boodschap, land, isocode);
