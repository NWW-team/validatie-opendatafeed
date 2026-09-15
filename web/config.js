// Publieke projectconfiguratie van Supabase.
//
// Hier hoort precies twee dingen te staan: de project-URL en de publishable
// key (in oudere projecten "anon public" genoemd). Die zijn ontworpen om in
// een browser te staan — ze zeggen wélk project je aanspreekt, niet wat je
// mag. Wat je mag, bepalen de policies in db/0001_toegang.sql.
//
// Hier hoort NOOIT te staan: de service-role key, de secret key, of het
// databasewachtwoord. Die geven volledige toegang en negeren RLS. Ze staan
// alleen in GitHub Actions als repository secret.
//
// Vul deze twee waarden in via Supabase → Project Settings → API Keys.
export const SUPABASE_URL = "";
export const SUPABASE_PUBLISHABLE_KEY = "";
