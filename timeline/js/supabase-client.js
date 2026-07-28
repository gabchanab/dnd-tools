const SUPABASE_URL = 'https://zmflgsgwqygfcxkutftg.supabase.co';
const SUPABASE_ANON_KEY = 'sb_publishable_LlZrTWPyrSSp59yDKq7hmw_QXuTMPWI';

// Assigned directly onto window (rather than a bare `const supabase`) so every
// later <script> tag reliably sees the real client instance, not the raw
// @supabase/supabase-js library namespace that the CDN script also calls "supabase".
window.supabase = window.supabase.createClient(SUPABASE_URL, SUPABASE_ANON_KEY);
