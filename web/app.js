// Inloggen, uitloggen en het ophalen van de afgeschermde bevindingen.
//
// Let op wat deze code wél en niet doet. Hij regelt de schermen: wie is
// ingelogd, wat is er te zien, wat zegt een foutmelding. Hij regelt géén
// toegang — dat doet de database. Elk verzoek hieronder gaat met de sessie
// van de gebruiker naar Supabase, en de policy in db/0001_toegang.sql
// beslist. Wie dit bestand aanpast, verandert de schermen, niet de regel.
//
// De opbouw van "rapport-inhoud" hieronder is met opzet dezelfde structuur
// en dezelfde rhc-*-klassen als render_html() in src/feedvalidator/report.py:
// samen vormen het openbare rapport en deze pagina één doorlopend geheel,
// met alleen het inlogscherm ertussen.

import { createClient } from "https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2/+esm";
import { SUPABASE_URL, SUPABASE_PUBLISHABLE_KEY } from "./config.js";

const el = (id) => document.getElementById(id);
const toon = (id, zichtbaar = true) => { el(id).hidden = !zichtbaar; };

const SEVERITEIT_VOLGORDE = { error: 0, warning: 1, info: 2 };
const SEVERITEIT_LABEL = { error: "Fout", warning: "Waarschuwing", info: "Informatief" };

if (!SUPABASE_URL || !SUPABASE_PUBLISHABLE_KEY) {
  toon("niet-geconfigureerd");
} else {
  start();
}

function start() {
  const supabase = createClient(SUPABASE_URL, SUPABASE_PUBLISHABLE_KEY);

  el("directe-url").textContent =
    `${SUPABASE_URL}/rest/v1/bevindingen?select=*&apikey=${SUPABASE_PUBLISHABLE_KEY}`;

  el("inlogformulier").addEventListener("submit", async (gebeurtenis) => {
    gebeurtenis.preventDefault();
    toon("inlogmelding", false);
    el("inlogknop").disabled = true;
    el("inlogknop").textContent = "Bezig…";

    const { error } = await supabase.auth.signInWithPassword({
      email: el("email").value.trim(),
      password: el("wachtwoord").value,
    });

    el("inlogknop").disabled = false;
    el("inlogknop").textContent = "Inloggen";

    if (error) {
      // Bewust één boodschap voor "bestaat niet" en "wachtwoord klopt niet",
      // zodat deze pagina niet verklapt welke adressen een account hebben.
      el("inlogmelding").textContent = "Inloggen is niet gelukt. Controleer het e-mailadres en het wachtwoord.";
      toon("inlogmelding");
      return;
    }
    el("wachtwoord").value = "";
  });

  el("uitlogknop").addEventListener("click", async () => {
    await supabase.auth.signOut();
  });

  // Eén plek die op de sessie reageert: bij het laden van de pagina, na
  // inloggen, na uitloggen, en als het token verloopt.
  supabase.auth.onAuthStateChange((_gebeurtenis, sessie) => teken(supabase, sessie));
  supabase.auth.getSession().then(({ data }) => teken(supabase, data.session));
}

async function teken(supabase, sessie) {
  if (!sessie) {
    toon("uitgelogd");
    toon("ingelogd", false);
    el("rapport-inhoud").replaceChildren();
    return;
  }

  toon("uitgelogd", false);
  toon("ingelogd");
  el("wie").textContent = sessie.user.email ?? "onbekend";

  // Vraag de database of dit account op de allowlist staat. Dit is voor de
  // boodschap op het scherm: het verschil tussen "niets gevonden" en "jij
  // mag dit niet zien". De policy op de tabellen staat er los van en geldt
  // ook als deze aanroep wordt overgeslagen.
  const { data: toegestaan, error } = await supabase.rpc("is_toegestaan");
  if (error || !toegestaan) {
    toon("geen-toegang");
    toon("wel-toegang", false);
    return;
  }

  toon("geen-toegang", false);
  toon("wel-toegang");
  await laadRapport(supabase);
}

async function laadRapport(supabase) {
  // Er hoort maar één rapport in de tabel te staan — de schrijfstap ruimt
  // oudere rondes op — maar we vragen toch expliciet de nieuwste met een id
  // om op te filteren. Zonder die filter tonen bevindingen van elke ronde
  // ooit geschreven, niet alleen de laatste.
  const { data: rapporten } = await supabase
    .from("rapporten")
    .select(
      "id, gegenereerd_op, base_url, samenvatting, regelresultaten, " +
        "buiten_beschouwing, gesloten_posten, fetch_fouten, datums_per_land",
    )
    .order("gegenereerd_op", { ascending: false })
    .limit(1);

  const rapport = rapporten?.[0];
  const inhoud = el("rapport-inhoud");
  inhoud.replaceChildren();

  if (!rapport) {
    el("rapportregel").textContent = "Nog geen ronde weggeschreven.";
    return;
  }

  const { data: bevindingen, error } = await supabase
    .from("bevindingen")
    .select("regel_id, regel_titel, zwaarte, boodschap, land")
    .eq("rapport_id", rapport.id)
    .order("regel_id");

  if (error) {
    el("rapportregel").textContent = "De gegevens konden niet worden opgehaald.";
    return;
  }

  el("rapportregel").textContent = `Ronde van ${new Date(rapport.gegenereerd_op).toLocaleString("nl-NL")}`;
  inhoud.append(...bouwRapport(rapport, bevindingen ?? []));
}

function bouwRapport(rapport, bevindingen) {
  const s = rapport.samenvatting ?? {};
  const gezond = (s.errors ?? 0) === 0 && Object.keys(rapport.fetch_fouten ?? {}).length === 0;
  const knopen = [];

  knopen.push(
    p(
      `Peilmoment ${new Date(rapport.gegenereerd_op).toLocaleString("nl-NL")} · ` +
        `feed ${rapport.base_url} · doorlooptijd ${(s.duration_seconds ?? 0).toFixed(1)}s`,
      "rhc-paragraph--subtle",
    ),
  );

  knopen.push(
    div(`rhc-alert rhc-alert--${gezond ? "ok" : "error"}`, [
      div(
        "rhc-alert__body",
        [],
        gezond
          ? "Geen blokkerende bevindingen: de feed voldoet aan alle harde regels."
          : `${s.errors ?? 0} blokkerende bevinding(en): de feed voldoet niet aan alle harde regels.`,
      ),
    ]),
  );

  const regelsMetBevinding = s.rules_failed ?? 0;
  const regelsTotaal = s.rules ?? 0;
  const tegels = [
    ["error", s.errors ?? 0, "Fouten"],
    ["warning", s.warnings ?? 0, "Waarschuwingen"],
    ["info", s.infos ?? 0, "Informatief"],
    ["ok", `${regelsTotaal - regelsMetBevinding}/${regelsTotaal}`, "Regels zonder bevinding"],
    ["ok", s.countries_checked ?? 0, "Landen gecontroleerd"],
  ];
  knopen.push(
    div(
      "rhc-data-summary",
      tegels.map(([variant, waarde, label]) =>
        div(`rhc-data-summary__item rhc-data-summary__item--${variant}`, [
          div("rhc-data-summary__value", [], String(waarde)),
          div("rhc-data-summary__label", [], label),
        ]),
      ),
    ),
  );

  const fetchFouten = Object.entries(rapport.fetch_fouten ?? {}).sort(([a], [b]) => a.localeCompare(b));
  if (fetchFouten.length) {
    knopen.push(h2("Endpoints die niet antwoordden"));
    knopen.push(
      ul(
        fetchFouten.map(([naam, fout]) => {
          const li = document.createElement("li");
          const sterk = document.createElement("strong");
          sterk.textContent = naam;
          li.append(sterk, ` — ${fout}`);
          return li;
        }),
      ),
    );
  }

  if ((rapport.buiten_beschouwing ?? []).length) {
    knopen.push(h2("Buiten beschouwing gelaten"));
    knopen.push(
      p(
        "Deze landen zijn op verzoek niet getoetst; ze tellen niet mee in de aantallen hierboven.",
        "rhc-paragraph--rule",
      ),
    );
    knopen.push(ul(rapport.buiten_beschouwing.map((naam) => li(naam))));
  }

  const regels = [...(rapport.regelresultaten ?? [])].sort(
    (a, b) =>
      Number(a.ok) - Number(b.ok) ||
      SEVERITEIT_VOLGORDE[a.zwaarte] - SEVERITEIT_VOLGORDE[b.zwaarte] ||
      b.bevindingen_aantal - a.bevindingen_aantal ||
      a.regel_id.localeCompare(b.regel_id),
  );

  knopen.push(h2("Resultaat per regel"));
  const tabel = document.createElement("div");
  tabel.className = "rhc-table-wrapper";
  const table = document.createElement("table");
  table.className = "rhc-table";
  table.innerHTML =
    "<thead><tr><th>Regel</th><th>Onderwerp</th><th>Status</th>" +
    '<th class="num">In orde</th><th class="num">Bevindingen</th></tr></thead>';
  const tbody = document.createElement("tbody");
  for (const r of regels) {
    const tr = document.createElement("tr");
    tr.append(
      td(r.regel_id),
      td(r.regel_titel),
      tdBadge(r.ok ? "ok" : r.zwaarte, r.ok ? "In orde" : SEVERITEIT_LABEL[r.zwaarte]),
      td(`${r.in_orde}/${r.gecontroleerd}`, "num"),
      td(String(r.bevindingen_aantal), "num"),
    );
    tbody.append(tr);
  }
  table.append(tbody);
  tabel.append(table);
  knopen.push(tabel);

  if ((rapport.gesloten_posten ?? []).length) {
    knopen.push(h2("Als gesloten aangemerkt"));
    knopen.push(
      p(
        "Deze posten zijn gesloten of opgeschort en hoeven daarom geen adres te hebben.",
        "rhc-paragraph--rule",
      ),
    );
    knopen.push(ul(rapport.gesloten_posten.map((naam) => li(naam))));
  }

  knopen.push(h2("Bevindingen"));
  const perRegel = new Map();
  for (const b of bevindingen) {
    if (!perRegel.has(b.regel_id)) perRegel.set(b.regel_id, []);
    perRegel.get(b.regel_id).push(b);
  }
  const blokken = regels.filter((r) => !r.ok);
  if (!blokken.length) {
    knopen.push(p("Geen enkele regel leverde een bevinding op.", "rhc-empty"));
  } else {
    for (const r of blokken) {
      const details = document.createElement("details");
      details.className = "rhc-accordion__section";
      details.open = true;
      const summary = document.createElement("summary");
      summary.append(
        `${r.regel_id} — ${r.regel_titel} `,
        badge(r.zwaarte, String(r.bevindingen_aantal)),
      );
      details.append(
        summary,
        p(r.beschrijving, "rhc-paragraph--rule"),
        ul(
          (perRegel.get(r.regel_id) ?? []).map((b) => {
            const item = li("");
            if (b.land) {
              const sterk = document.createElement("strong");
              sterk.textContent = b.land;
              item.append(sterk, ` — ${b.boodschap}`);
            } else {
              item.textContent = b.boodschap;
            }
            return item;
          }),
        ),
      );
      knopen.push(details);
    }
  }

  knopen.push(h2("Datums per land"));
  knopen.push(
    p(
      "De drie datums van elk land naast elkaar, zonder oordeel — de regel " +
        "hierboven (L12) duidt alleen de afwijkingen.",
      "rhc-paragraph--rule",
    ),
  );
  const datumsTabel = document.createElement("div");
  datumsTabel.className = "rhc-table-wrapper";
  const datumsTable = document.createElement("table");
  datumsTable.className = "rhc-table";
  datumsTable.innerHTML =
    "<thead><tr><th>Land</th><th>ISO</th><th>Getoond</th><th>Gewijzigd</th><th>Gepusht</th></tr></thead>";
  const datumsBody = document.createElement("tbody");
  for (const d of rapport.datums_per_land ?? []) {
    const tr = document.createElement("tr");
    tr.append(td(d.location), td(d.isocode), tdDatum(d.shown), tdDatum(d.modified), tdDatum(d.pushed));
    datumsBody.append(tr);
  }
  datumsTable.append(datumsBody);
  datumsTabel.append(datumsTable);
  knopen.push(datumsTabel);

  return knopen;
}

// -- kleine DOM-helpers, geen innerHTML met opgehaalde tekst erin ---------

function div(klasse, kinderen = [], tekst) {
  const node = document.createElement("div");
  node.className = klasse;
  if (tekst !== undefined) node.textContent = tekst;
  node.append(...kinderen);
  return node;
}

function p(tekst, klasse) {
  const node = document.createElement("p");
  node.className = klasse ? `nl-paragraph ${klasse}` : "nl-paragraph";
  node.textContent = tekst;
  return node;
}

function h2(tekst) {
  const node = document.createElement("h2");
  node.className = "rhc-heading nl-heading--level-2";
  node.textContent = tekst;
  return node;
}

function ul(items) {
  const node = document.createElement("ul");
  node.className = "rhc-unordered-list";
  node.append(...items);
  return node;
}

function li(tekst) {
  const node = document.createElement("li");
  node.textContent = tekst;
  return node;
}

function td(tekst, klasse) {
  const node = document.createElement("td");
  if (klasse) node.className = klasse;
  node.textContent = tekst;
  return node;
}

function tdDatum(isoDatum) {
  // De datums komen als "2026-09-15" binnen; tonen doen we ze Nederlands.
  if (!isoDatum) {
    const leeg = document.createElement("td");
    const streep = document.createElement("span");
    streep.className = "rhc-empty";
    streep.textContent = "—";
    leeg.append(streep);
    return leeg;
  }
  const [jaar, maand, dag] = isoDatum.split("-");
  return td(`${dag}-${maand}-${jaar}`);
}

function badge(variant, tekst) {
  const node = document.createElement("span");
  node.className = `rhc-badge rhc-badge--${variant}`;
  node.textContent = tekst;
  return node;
}

function tdBadge(variant, tekst) {
  const node = document.createElement("td");
  node.append(badge(variant, tekst));
  return node;
}
