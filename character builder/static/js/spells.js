const OPEN5E_API_BASE = 'https://api.open5e.com/v2';

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

  const res = await fetch(`${OPEN5E_API_BASE}/spells/?${params}`);
  if (!res.ok) throw new Error(`API error ${res.status}`);
  const data = await res.json();

  let spells = (data.results || []).map(s => ({
    ...s,
    index: s.index || s.key || '',
    school: s.school?.key || s.school || '',
  }));

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
  const res = await fetch(`${OPEN5E_API_BASE}/spells/${idx}/`);
  if (!res.ok) throw new Error(`API error ${res.status}`);
  const raw = await res.json();
  return normaliseSpell(idx, raw);
}
