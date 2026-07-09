const OPEN5E_API_BASE = 'https://api.open5e.com/v2';
const OPEN5E_FETCH_TIMEOUT_MS = 12000;

async function fetchOpen5e(url) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), OPEN5E_FETCH_TIMEOUT_MS);
  try {
    return await fetch(url, { signal: controller.signal });
  } catch (e) {
    if (e.name === 'AbortError') {
      throw new Error(`Open5e didn't respond within ${OPEN5E_FETCH_TIMEOUT_MS / 1000}s. It may be down — try again shortly.`);
    }
    throw e;
  } finally {
    clearTimeout(timer);
  }
}

// Reformat the raw open5e response into the flat shape the rest of the app expects.
// This mirrors what the old Flask /api/spells/<id> endpoint used to return.
function normaliseSpell(idx, raw) {
  const components = [
    raw.verbal && 'V',
    raw.somatic && 'S',
    raw.material && 'M',
  ].filter(Boolean).join(', ');

  const desc = Array.isArray(raw.desc) ? raw.desc : (raw.desc ? [raw.desc] : []);
  const higher_level = Array.isArray(raw.higher_level) ? raw.higher_level : (raw.higher_level ? [raw.higher_level] : []);

  return {
    index: idx,
    name: raw.name || 'Unknown',
    level: raw.level ?? 0,
    school_index: raw.school?.key || '',
    school_name: raw.school?.name || '',
    casting_time: raw.casting_time || '',
    range: raw.range_text || raw.range || '',
    duration: raw.duration || '',
    components,
    material: raw.material_specified || '',
    ritual: raw.ritual || false,
    concentration: raw.concentration || false,
    desc,
    higher_level,
    classes: (raw.classes || []).map(c => c.name || ''),
  };
}

// Mirrors the old Flask /api/spells/search endpoint: only `level` is filtered
// server-side reliably, the rest are applied client-side against the full list.
async function searchSpells({ level = '', school = '', class: cls = '', name = '' } = {}) {
  const params = new URLSearchParams({ document__key: 'srd-2024', limit: 1000 });
  if (level !== '') params.append('level', level);

  const res = await fetchOpen5e(`${OPEN5E_API_BASE}/spells/?${params}`);
  if (!res.ok) throw new Error(`API error ${res.status}`);
  const data = await res.json();

  let spells = (data.results || []).map(s => ({
    ...s,
    index: s.index || s.key || '',
    school: s.school?.key || s.school || '',
  }));

  // Homebrew spells are already stored in the final normalised shape (school_index,
  // classes as plain name strings) — alias them into the shape this function's own
  // filters expect (school key, classes as {name} objects) rather than touching the
  // filters themselves.
  const { data: hbRows } = await supabase.from('homebrew_items').select('id,data').eq('type', 'spell');
  const hbSpells = (hbRows || []).map(row => ({
    ...row.data,
    index: 'hb-' + row.id,
    school: row.data.school_index || '',
    classes: (row.data.classes || []).map(c => ({ name: c })),
  }));
  spells = spells.concat(hbSpells);

  const schLower = school.toLowerCase();
  if (schLower) spells = spells.filter(s => s.school === schLower);

  const clsLower = cls.toLowerCase();
  if (clsLower) {
    spells = spells.filter(s =>
      (s.classes || []).some(c =>
        c.name?.toLowerCase() === clsLower || c.key?.toLowerCase().split('_').pop() === clsLower
      )
    );
  }

  const nmLower = name.trim().toLowerCase();
  if (nmLower) spells = spells.filter(s => s.name.toLowerCase().includes(nmLower));

  return { results: spells };
}

async function getSpellDetail(idx) {
  if (idx.startsWith('hb-')) {
    const id = idx.slice(3);
    const { data, error } = await supabase.from('homebrew_items').select('data').eq('id', id).single();
    if (error || !data) throw new Error('Homebrew spell not found');
    return data.data;
  }
  const res = await fetchOpen5e(`${OPEN5E_API_BASE}/spells/${idx}/`);
  if (!res.ok) throw new Error(`API error ${res.status}`);
  const raw = await res.json();
  return normaliseSpell(idx, raw);
}
