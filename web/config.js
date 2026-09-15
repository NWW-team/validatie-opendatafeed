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
// Project: rckbrn's validatietool (eu-west-1).
export const SUPABASE_URL = "https://tkfasdijhdthywxorqwa.supabase.co";
export const SUPABASE_PUBLISHABLE_KEY = "sb_publishable_iRCBGhmdxfwtqCx0P3UbRQ_mUOMRZ7m";
