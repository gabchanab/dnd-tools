const SPELL_SLOTS = {
  full: {1:[2],2:[3],3:[4,2],4:[4,3],5:[4,3,2],6:[4,3,3],7:[4,3,3,1],
         8:[4,3,3,2],9:[4,3,3,3,1],10:[4,3,3,3,2],11:[4,3,3,3,2,1],
         12:[4,3,3,3,2,1],13:[4,3,3,3,2,1,1],14:[4,3,3,3,2,1,1],
         15:[4,3,3,3,2,1,1,1],16:[4,3,3,3,2,1,1,1],17:[4,3,3,3,2,1,1,1,1],
         18:[4,3,3,3,3,1,1,1,1],19:[4,3,3,3,3,2,1,1,1],20:[4,3,3,3,3,2,2,1,1]},
  half: {1:[2],2:[2],3:[3],4:[3],5:[4,2],6:[4,2],7:[4,3],
         8:[4,3],9:[4,3,2],10:[4,3,2],11:[4,3,3],
         12:[4,3,3],13:[4,3,3,1],14:[4,3,3,1],
         15:[4,3,3,2],16:[4,3,3,2],17:[4,3,3,3,1],
         18:[4,3,3,3,1],19:[4,3,3,3,2],20:[4,3,3,3,2]},
  pact: {1:[1],2:[2],3:[0,2],4:[0,2],5:[0,0,2],6:[0,0,2],7:[0,0,0,2],
         8:[0,0,0,2],9:[0,0,0,0,2],10:[0,0,0,0,2],11:[0,0,0,0,3],
         12:[0,0,0,0,3],13:[0,0,0,0,3],14:[0,0,0,0,3],
         15:[0,0,0,0,3],16:[0,0,0,0,3],17:[0,0,0,0,4],
         18:[0,0,0,0,4],19:[0,0,0,0,4],20:[0,0,0,0,4]},
};

const SKILL_AB = {
  "Acrobatics": "dexterity", "Animal Handling": "wisdom", "Arcana": "intelligence",
  "Athletics": "strength", "Deception": "charisma", "History": "intelligence",
  "Insight": "wisdom", "Intimidation": "charisma", "Investigation": "intelligence",
  "Medicine": "wisdom", "Nature": "intelligence", "Perception": "wisdom",
  "Performance": "charisma", "Persuasion": "charisma", "Religion": "intelligence",
  "Sleight of Hand": "dexterity", "Stealth": "dexterity", "Survival": "wisdom",
};

function mod(score) { return Math.floor((score - 10) / 2); }
function fmt(n) { return n >= 0 ? `+${n}` : `${n}`; }

function parseData(raw) {
  if (!raw) return {};
  if (typeof raw === 'object') return raw;
  try { return JSON.parse(raw); } catch { return {}; }
}

function buildCharacterContext(f) {
  const sp  = parseData(f.species_data);
  const cls = parseData(f.class_data);
  const bg  = parseData(f.bg_data);
  const sub = parseData(f.subclass_data);

  const sc = {
    strength:     parseInt(f.str ?? 10, 10),
    dexterity:    parseInt(f.dex ?? 10, 10),
    constitution: parseInt(f.con ?? 10, 10),
    intelligence: parseInt(f.int ?? 10, 10),
    wisdom:       parseInt(f.wis ?? 10, 10),
    charisma:     parseInt(f.cha ?? 10, 10),
  };

  const level = parseInt(f.level ?? 1, 10);
  const prof = Math.max(2, Math.floor((level - 1) / 4) + 2);

  // HP — respect builder overrides (custom die selection, rolled HP)
  let hitDie;
  if (f.hit_die_override) {
    hitDie = Math.max(4, parseInt(f.hit_die_override, 10));
  } else {
    const hitDiceStr = (cls.hit_points || {}).hit_dice || 'D8';
    const digits = hitDiceStr.replace(/\D/g, '');
    hitDie = parseInt(digits || '8', 10);
  }

  let hpMax;
  if (f.hp_rolled && parseInt(f.hp_rolled, 10) > 0) {
    hpMax = Math.max(1, parseInt(f.hp_rolled, 10));
  } else {
    hpMax = hitDie + mod(sc.constitution) + (level - 1) * (Math.floor(hitDie / 2) + 1 + mod(sc.constitution));
    hpMax = Math.max(1, hpMax);
  }
  const hpTemp = 0;

  // Skills
  const chosen = (f.skills || []).map(s => s.toLowerCase());
  const skillsOut = Object.entries(SKILL_AB).map(([sk, ab]) => {
    const base = mod(sc[ab]);
    const ip = chosen.includes(sk.toLowerCase());
    return {
      name: sk, ability: ab.slice(0, 3).toUpperCase(),
      base_mod: base,
      bonus: base + (ip ? prof : 0),
      proficiency: ip ? 'proficient' : 'none',
    };
  });

  // Saving throws
  const rawSaves = cls.saving_throws || [];
  const saveProfs = rawSaves.map(s => (typeof s === 'object' ? (s.name || '') : s).toLowerCase());

  const ABS = ['strength', 'dexterity', 'constitution', 'intelligence', 'wisdom', 'charisma'];
  const abilitiesOut = ABS.map(ab => {
    const score = sc[ab], m = mod(score);
    const isp = saveProfs.includes(ab) || saveProfs.includes(ab.slice(0, 3));
    return {
      key: ab, label: ab.slice(0, 3).toUpperCase(), score,
      modifier: m, save: m + (isp ? prof : 0), save_prof: isp,
    };
  });

  const perceptionSkill = skillsOut.find(s => s.name === 'Perception');
  const passivePerc = 10 + (perceptionSkill ? perceptionSkill.bonus : mod(sc.wisdom));

  // Speed from species traits
  let speedVal = 30;
  for (const t of (sp.traits || [])) {
    if (t && typeof t === 'object' && t.type === 'SPEED') {
      const m = /\d+/.exec(t.desc || '30');
      if (m) { speedVal = parseInt(m[0], 10); break; }
    }
  }

  // Spell slots
  const ct = (cls.caster_type || 'NONE').toLowerCase();
  const slotTable = ct === 'full' ? SPELL_SLOTS.full : ct === 'half' ? SPELL_SLOTS.half : ct === 'pact' ? SPELL_SLOTS.pact : {};
  const slotList = slotTable[level] || [];
  const spellSlots = slotList
    .map((n, i) => ({ level: i + 1, max: n, used: 0, available: n }))
    .filter(s => s.max > 0);

  // Spellcasting stats — derived from "Spellcasting" or "Pact Magic" feature description
  let spellModDisplay = null, spellAttackDisplay = null, spellSaveDc = null, spellAbilityAbbr = '';
  if (['full', 'half', 'pact'].includes(ct)) {
    for (const feat of (cls.features || [])) {
      if (feat.name === 'Spellcasting' || feat.name === 'Pact Magic') {
        const m = /(Intelligence|Wisdom|Charisma) is (?:your |the )?spellcasting ability/i.exec(feat.desc || '');
        if (m) {
          const ability = m[1].toLowerCase();
          spellAbilityAbbr = ability.slice(0, 3).toUpperCase();
          const scMod = mod(sc[ability]);
          spellModDisplay = fmt(scMod);
          spellAttackDisplay = fmt(scMod + prof);
          spellSaveDc = 8 + scMod + prof;
        }
        break;
      }
    }
  }

  // Species traits
  const traitsOut = (sp.traits || [])
    .filter(t => t && typeof t === 'object' && t.name)
    .map(t => ({ name: t.name || '', desc: t.desc || '' }));

  // Class features — exclude spellcasting mechanics (handled by spell step)
  const SKIP_FEAT_NAMES = new Set(['Spellcasting']);
  const classFeatures = [];
  for (const feat of (cls.features || [])) {
    const levels = (feat.gained_at || []).filter(g => g && typeof g === 'object').map(g => g.level);
    const ft = feat.feature_type || '';
    const name = feat.name || '';
    if (SKIP_FEAT_NAMES.has(name) || name.endsWith('Spell List')) continue;
    if ((ft === 'CLASS_LEVEL_FEATURE' || ft === 'PROFICIENCIES') && (!levels.length || levels.some(l => l <= level))) {
      classFeatures.push({ name, desc: feat.desc || '' });
    }
  }

  // Subclass features (level-gated)
  const subclassFeatures = [];
  if (sub && Object.keys(sub).length) {
    const hbData = sub._hbData;
    if (hbData) {
      // Homebrew JSON: features dict keyed by level string e.g. {"3": [...], "7": [...]}
      const levelKeys = Object.keys(hbData.features || {}).sort((a, b) => parseInt(a, 10) - parseInt(b, 10));
      for (const levelStr of levelKeys) {
        if (parseInt(levelStr, 10) <= level) {
          for (const feat of (hbData.features[levelStr] || [])) {
            subclassFeatures.push({ name: feat.name || '', desc: feat.description || '' });
          }
        }
      }
    } else {
      // Open5e: features list with gained_at
      for (const feat of (sub.features || [])) {
        const levels = (feat.gained_at || []).filter(g => g && typeof g === 'object').map(g => g.level);
        if (levels.length && levels.some(l => l <= level)) {
          subclassFeatures.push({ name: feat.name || '', desc: feat.desc || '' });
        }
      }
    }
  }

  // Parse CORE_TRAITS_TABLE rows for class proficiencies and equipment
  let classEquipment = '', armorProficiencies = '', weaponProficiencies = '';
  const coreTraits = (cls.features || []).find(feat => feat.feature_type === 'CORE_TRAITS_TABLE');
  if (coreTraits) {
    for (const row of (coreTraits.desc || '').split('\n')) {
      const cells = row.split('|').map(c => c.trim()).filter(Boolean);
      if (cells.length < 2) continue;
      const label = cells[0].toLowerCase();
      if (label === 'starting equipment') classEquipment = cells[1];
      else if (label === 'armor training') armorProficiencies = cells[1];
      else if (label === 'weapon proficiencies') weaponProficiencies = cells[1];
    }
  }

  // Background benefits — equipment, tool proficiency, languages
  let bgEquipment = '', bgToolProficiency = '', bgLanguages = '';
  let bgTraitName = '', bgTraitDesc = '', bgOfeatName = '', bgOfeatDesc = '';
  const bgBenefits = bg.benefits || [];
  if (bgBenefits.length) {
    for (const b of bgBenefits) {
      const t = b.type || '';
      if (t === 'equipment' && !bgEquipment) bgEquipment = b.desc || '';
      if (t === 'tool_proficiency' && !bgToolProficiency) bgToolProficiency = b.desc || '';
      if (t === 'language' && !bgLanguages) bgLanguages = b.desc || '';
      if (t === 'trait' && !bgTraitName) { bgTraitName = b.name || ''; bgTraitDesc = b.desc || ''; }
      if (t === 'feat' && !bgOfeatName) { bgOfeatName = b.name || ''; bgOfeatDesc = b.desc || ''; }
    }
  } else {
    const flat = bg.starting_equipment || [];
    if (flat.length) bgEquipment = flat.join(', ');
    bgToolProficiency = bg.tool_proficiency || '';
    bgLanguages = bg.languages || '';
    bgTraitName = (bg.trait || {}).name || '';
    bgTraitDesc = (bg.trait || {}).desc || '';
    bgOfeatName = (bg.feat || {}).name || '';
    bgOfeatDesc = (bg.feat || {}).desc || '';
  }

  const preparedSpells = (f.spells || [])
    .map(s => (typeof s === 'object' ? { name: s.name, level: s.level ?? null, index: s.index ?? null } : { name: s, level: null, index: null }))
    .sort((a, b) => (a.level ?? 99) - (b.level ?? 99));

  return {
    char_name: f.name || 'Unnamed Hero',
    player_name: f.player_name || '',
    alignment: f.alignment || 'True Neutral',
    species_name: sp.name || f.species_name || '',
    class_name: cls.name || f.class_name || '',
    subclass_name: f.subclass_name || '',
    subclass_homebrew: f.subclass_homebrew || false,
    background_name: bg.name || f.background_name || '',
    level,
    proficiency_bonus: prof,
    passive_perception: passivePerc,
    hp_max: hpMax,
    hp_current: hpMax,
    hp_temp: hpTemp,
    hp_pct: 100,
    hit_dice_display: `${level}d${hitDie}`,
    armor_class: 10 + mod(sc.dexterity),
    speed: speedVal,
    initiative: fmt(mod(sc.dexterity)),
    inspiration: true,
    spell_mod: spellModDisplay,
    spell_attack: spellAttackDisplay,
    spell_save_dc: spellSaveDc,
    spell_ability: spellAbilityAbbr,
    abilities: abilitiesOut,
    skills: skillsOut,
    spell_slots: spellSlots,
    traits: traitsOut,
    class_features: classFeatures,
    subclass_features: subclassFeatures,
    resources: [],
    prepared_spells: preparedSpells,
    cantrips: f.cantrips || [],
    notes: f.notes || '',
    backstory: f.backstory || '',
    gold: parseFloat(f.gold ?? 0),
    class_equipment: classEquipment,
    bg_equipment: bgEquipment,
    armor_proficiencies: armorProficiencies,
    weapon_proficiencies: weaponProficiencies,
    bg_tool_proficiency: bgToolProficiency,
    bg_languages: bgLanguages,
    bg_trait_name: bgTraitName,
    bg_trait_desc: bgTraitDesc,
    bg_ofeat_name: bgOfeatName,
    bg_ofeat_desc: bgOfeatDesc,
  };
}
