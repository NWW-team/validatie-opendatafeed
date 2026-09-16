// Start een nieuwe validatieronde namens een ingelogde, toegestane gebruiker.
//
// Waarom deze functie bestaat: een workflow starten vraagt een GitHub-token
// met schrijfrecht op Actions, en de afgeschermde pagina is een statisch
// bestand op GitHub Pages. Alles wat die pagina kent, kent de bezoeker ook.
// Het token staat daarom hier, als secret van deze functie, en de browser
// krijgt het nooit te zien — die stuurt alleen zijn eigen sessie mee.
//
// Deze functie beslist niet zelf wie mag wat. Ze vraagt het na bij dezelfde
// bron als de rest van de pagina: auth.getUser() voor "ben je ingelogd" en
// is_toegestaan() voor "sta je op de allowlist". Wie de allowlist aanpast in
// db/0001_toegang.sql, past daarmee ook aan wie deze knop mag gebruiken.

import { createClient } from "jsr:@supabase/supabase-js@2";

const REPO = "NWW-team/validatie-opendatafeed";
const WORKFLOW = "publiceer-rapport.yml";
const TAK = "main";

// Alleen de gepubliceerde pagina mag deze functie aanroepen. Een andere
// herkomst krijgt geen CORS-toestemming en komt dus niet door de browser heen.
const TOEGESTANE_HERKOMST = "https://nww-team.github.io";

const cors = {
  "Access-Control-Allow-Origin": TOEGESTANE_HERKOMST,
  "Access-Control-Allow-Headers": "authorization, content-type, apikey",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
};

function antwoord(status: number, lichaam: Record<string, unknown>): Response {
  return new Response(JSON.stringify(lichaam), {
    status,
    headers: { ...cors, "Content-Type": "application/json" },
  });
}

Deno.serve(async (verzoek) => {
  if (verzoek.method === "OPTIONS") return new Response(null, { status: 204, headers: cors });
  if (verzoek.method !== "POST") return antwoord(405, { fout: "Alleen POST." });

  const token = Deno.env.get("GITHUB_DISPATCH_TOKEN");
  if (!token) {
    // Zonder secret is de knop niet bruikbaar. Zeg dat met zoveel woorden in
    // plaats van een vage 500, anders is dit uren zoeken.
    return antwoord(503, {
      fout: "Deze functie heeft nog geen GITHUB_DISPATCH_TOKEN; zie docs/toegang.md.",
    });
  }

  const meegestuurd = verzoek.headers.get("Authorization") ?? "";
  const supabase = createClient(
    Deno.env.get("SUPABASE_URL")!,
    Deno.env.get("SUPABASE_ANON_KEY")!,
    { global: { headers: { Authorization: meegestuurd } } },
  );

  const { data: { user } } = await supabase.auth.getUser();
  if (!user) return antwoord(401, { fout: "Niet ingelogd." });

  const { data: toegestaan, error } = await supabase.rpc("is_toegestaan");
  if (error || !toegestaan) return antwoord(403, { fout: "Dit account staat niet op de allowlist." });

  const github = {
    Authorization: `Bearer ${token}`,
    Accept: "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
    "User-Agent": "validatie-opendatafeed",
  };

  // Loopt er al een ronde, start er dan geen tweede. De workflow zet ze met
  // concurrency toch achter elkaar, en twee rondes vlak na elkaar leveren
  // hetzelfde antwoord op terwijl ze de feed dubbel belasten.
  const lopend = await fetch(
    `https://api.github.com/repos/${REPO}/actions/workflows/${WORKFLOW}/runs?per_page=10`,
    { headers: github },
  );
  if (lopend.ok) {
    const { workflow_runs = [] } = await lopend.json();
    const bezig = workflow_runs.find((r: { status: string }) => r.status !== "completed");
    if (bezig) return antwoord(409, { fout: "Er loopt al een ronde.", run: bezig.html_url });
  }

  const gestart = await fetch(
    `https://api.github.com/repos/${REPO}/actions/workflows/${WORKFLOW}/dispatches`,
    { method: "POST", headers: github, body: JSON.stringify({ ref: TAK }) },
  );
  if (!gestart.ok) {
    // De tekst van GitHub niet doorgeven aan de browser: die kan details over
    // de repo of het token bevatten. In de functielog staat hij wel.
    console.error(`workflow_dispatch gaf HTTP ${gestart.status}: ${await gestart.text()}`);
    return antwoord(502, { fout: `GitHub weigerde de start (HTTP ${gestart.status}).` });
  }

  console.log(`Ronde gestart door ${user.email}.`);
  return antwoord(202, { gestart: true });
});
