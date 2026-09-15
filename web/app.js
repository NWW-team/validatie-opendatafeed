// Inloggen, uitloggen en het ophalen van de afgeschermde bevindingen.
//
// Let op wat deze code wél en niet doet. Hij regelt de schermen: wie is
// ingelogd, wat is er te zien, wat zegt een foutmelding. Hij regelt géén
// toegang — dat doet de database. Elk verzoek hieronder gaat met de sessie
// van de gebruiker naar Supabase, en de policy in db/0001_toegang.sql
// beslist. Wie dit bestand aanpast, verandert de schermen, niet de regel.

import { createClient } from "https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2/+esm";
import { SUPABASE_URL, SUPABASE_PUBLISHABLE_KEY } from "./config.js";

const el = (id) => document.getElementById(id);
const toon = (id, zichtbaar = true) => { el(id).hidden = !zichtbaar; };

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
    el("bevindingen").replaceChildren();
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
  await laadBevindingen(supabase);
}

async function laadBevindingen(supabase) {
  // Er hoort maar één rapport in de tabel te staan — de schrijfstap ruimt
  // oudere rondes op — maar we vragen toch expliciet de nieuwste met een id
  // om op te filteren. Zonder die filter tonen bevindingen van elke ronde
  // ooit geschreven, niet alleen de laatste.
  const { data: rapporten } = await supabase
    .from("rapporten")
    .select("id, gegenereerd_op, samenvatting")
    .order("gegenereerd_op", { ascending: false })
    .limit(1);

  const rapport = rapporten?.[0];
  el("rapportregel").textContent = rapport
    ? `Ronde van ${new Date(rapport.gegenereerd_op).toLocaleString("nl-NL")}`
    : "Nog geen ronde weggeschreven.";

  const lichaam = el("bevindingen");
  lichaam.replaceChildren();

  if (!rapport) {
    toon("leegmelding", true);
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

  toon("leegmelding", (bevindingen ?? []).length === 0);

  for (const bevinding of bevindingen ?? []) {
    const rij = document.createElement("tr");
    rij.append(
      cel(bevinding.regel_id, { titel: bevinding.regel_titel }),
      cel(null, { badge: bevinding.zwaarte }),
      cel(bevinding.land ?? "—"),
      cel(bevinding.boodschap, { klasse: "boodschap" }),
    );
    lichaam.append(rij);
  }
}

function cel(tekst, { klasse, titel, badge } = {}) {
  const td = document.createElement("td");
  if (badge) {
    const span = document.createElement("span");
    span.className = `badge badge-${badge}`;
    span.textContent = badge;
    td.append(span);
  } else {
    td.textContent = tekst;
  }
  if (klasse) td.className = klasse;
  if (titel) td.title = titel;
  return td;
}
