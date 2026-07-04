"""
D&D 2024 Character Data Model
==============================
Designed for:
  - Full 2024 PHB rules compatibility
  - Homebrew/custom subclasses, traits, backgrounds, species
  - JSON serialisation for save/load
  - Clean separation between rules content and character state

Architecture
------------
  Content layer   — immutable definitions (classes, subclasses, feats, spells...)
  Character layer — mutable state (your specific character's choices and stats)
  Registry        — loads both official and homebrew content from JSON files
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
import json
import os


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class AbilityScore(str, Enum):
    STR = "strength"
    DEX = "dexterity"
    CON = "constitution"
    INT = "intelligence"
    WIS = "wisdom"
    CHA = "charisma"


class ProficiencyLevel(str, Enum):
    NONE       = "none"
    HALF       = "half"          # 2024: Bard's Jack of All Trades
    PROFICIENT = "proficient"
    EXPERT     = "expert"        # double proficiency bonus


class SpellcastingType(str, Enum):
    NONE      = "none"
    FULL      = "full"           # Wizard, Cleric, Druid, Bard, Sorcerer, Warlock
    HALF      = "half"           # Paladin, Ranger
    THIRD     = "third"          # Eldritch Knight, Arcane Trickster
    PACT      = "pact"           # Warlock (separate slot progression)


class RestoreOn(str, Enum):
    SHORT = "short_rest"
    LONG  = "long_rest"


class DamageType(str, Enum):
    ACID        = "acid"
    BLUDGEONING = "bludgeoning"
    COLD        = "cold"
    FIRE        = "fire"
    FORCE       = "force"
    LIGHTNING   = "lightning"
    NECROTIC    = "necrotic"
    PIERCING    = "piercing"
    POISON      = "poison"
    PSYCHIC     = "psychic"
    RADIANT     = "radiant"
    SLASHING    = "slashing"
    THUNDER     = "thunder"


class WeaponCategory(str, Enum):
    SIMPLE  = "simple"
    MARTIAL = "martial"


class ArmorCategory(str, Enum):
    LIGHT  = "light"
    MEDIUM = "medium"
    HEAVY  = "heavy"
    SHIELD = "shield"


# ---------------------------------------------------------------------------
# Content layer — immutable rule definitions
# ---------------------------------------------------------------------------

@dataclass
class Trait:
    """
    A single named feature, ability, or passive effect.
    Used for racial traits, class features, background features, and feats.

    homebrew=True marks content you've defined yourself — the rules engine
    will still apply it; it just helps you track what's official.
    """
    id: str                              # unique key, e.g. "darkvision", "rage"
    name: str
    description: str
    source: str                          # "PHB2024", "homebrew", "XGtE", etc.
    homebrew: bool = False

    # Optional mechanical tags — used by the rules engine for automation.
    # Free-form so you can add anything without modifying the dataclass.
    # Examples:
    #   {"type": "resistance", "damage_type": "fire"}
    #   {"type": "advantage", "on": "perception"}
    #   {"type": "bonus_action", "action": "second_wind"}
    mechanics: dict = field(default_factory=dict)


@dataclass
class Feat:
    """
    2024 PHB feat — includes Origin, General, Fighting Style, and Epic Boon feats.
    Repeatable feats (e.g. Fighting Style) set repeatable=True.
    """
    id: str
    name: str
    description: str
    source: str
    homebrew: bool = False
    category: str = "general"           # "origin", "general", "fighting_style", "epic_boon"
    prerequisites: list[str] = field(default_factory=list)
    repeatable: bool = False
    ability_score_improvement: Optional[AbilityScore] = None
    asi_amount: int = 0
    granted_traits: list[Trait] = field(default_factory=list)
    mechanics: dict = field(default_factory=dict)


@dataclass
class Subclass:
    """
    A subclass definition. Because many subclasses aren't in public APIs
    (and DnDBeyond locks them behind purchases), this is designed to be
    authored in JSON and loaded at runtime — see ContentRegistry below.

    features is a dict keyed by level: {3: [Trait, ...], 7: [...], ...}
    """
    id: str
    name: str
    parent_class_id: str
    description: str
    source: str
    homebrew: bool = False
    features: dict = field(default_factory=dict)          # {int: [Trait]}
    spellcasting_type: SpellcastingType = SpellcastingType.NONE
    subclass_spell_list: list[str] = field(default_factory=list)


@dataclass
class CharacterClass:
    id: str
    name: str
    description: str
    source: str
    homebrew: bool = False
    hit_die: int = 8
    primary_ability: list[AbilityScore] = field(default_factory=list)
    saving_throw_proficiencies: list[AbilityScore] = field(default_factory=list)
    armor_proficiencies: list[ArmorCategory] = field(default_factory=list)
    weapon_proficiencies: list[WeaponCategory] = field(default_factory=list)
    tool_proficiencies: list[str] = field(default_factory=list)
    skill_choices: int = 2
    skill_options: list[str] = field(default_factory=list)
    spellcasting_type: SpellcastingType = SpellcastingType.NONE
    spellcasting_ability: Optional[AbilityScore] = None
    features: dict = field(default_factory=dict)          # {int: [Trait]}
    subclass_level: int = 3


@dataclass
class Species:
    """
    2024 PHB uses 'Species' instead of 'Race'.
    Species no longer grant fixed ASIs — those come from Background instead.
    """
    id: str
    name: str
    description: str
    source: str
    homebrew: bool = False
    size: str = "medium"
    base_speed: int = 30
    traits: list[Trait] = field(default_factory=list)
    languages: list[str] = field(default_factory=list)


@dataclass
class Background:
    """
    2024 PHB Backgrounds grant: 2 skill proficiencies, 1 tool proficiency,
    1 language, starting equipment, and a feat (always an Origin feat).
    In 2024, backgrounds also provide the character's ASI (+2/+1).
    """
    id: str
    name: str
    description: str
    source: str
    homebrew: bool = False
    skill_proficiencies: list[str] = field(default_factory=list)
    tool_proficiency: Optional[str] = None
    languages: int = 1
    origin_feat_id: Optional[str] = None
    starting_equipment: list[str] = field(default_factory=list)
    feature: Optional[Trait] = None


@dataclass
class Spell:
    id: str
    name: str
    level: int                           # 0 = cantrip
    school: str
    casting_time: str
    range: str
    components: str
    duration: str
    description: str
    source: str
    homebrew: bool = False
    classes: list[str] = field(default_factory=list)
    ritual: bool = False
    concentration: bool = False
    upcast_description: Optional[str] = None


@dataclass
class Equipment:
    id: str
    name: str
    description: str
    source: str
    homebrew: bool = False
    weight: float = 0.0
    cost_gp: float = 0.0
    damage_dice: Optional[str] = None
    damage_type: Optional[DamageType] = None
    weapon_category: Optional[WeaponCategory] = None
    weapon_properties: list[str] = field(default_factory=list)
    armor_category: Optional[ArmorCategory] = None
    base_ac: Optional[int] = None
    max_dex_bonus: Optional[int] = None
    stealth_disadvantage: bool = False


# ---------------------------------------------------------------------------
# Character layer — mutable state
# ---------------------------------------------------------------------------

@dataclass
class AbilityScores:
    strength:     int = 10
    dexterity:    int = 10
    constitution: int = 10
    intelligence: int = 10
    wisdom:       int = 10
    charisma:     int = 10

    def get(self, ability: AbilityScore) -> int:
        return getattr(self, ability.value)

    def modifier(self, ability: AbilityScore) -> int:
        return (self.get(ability) - 10) // 2


@dataclass
class SkillEntry:
    name: str
    governing_ability: AbilityScore
    proficiency: ProficiencyLevel = ProficiencyLevel.NONE
    override_ability: Optional[AbilityScore] = None


@dataclass
class ClassLevel:
    class_id: str
    level: int
    subclass_id: Optional[str] = None
    level_choices: dict = field(default_factory=dict)  # {int: {choice dict}}


@dataclass
class SpellSlots:
    max_slots: dict = field(default_factory=lambda: {i: 0 for i in range(1, 10)})
    used_slots: dict = field(default_factory=lambda: {i: 0 for i in range(1, 10)})
    pact_slot_level: int = 0
    pact_slots_max: int = 0
    pact_slots_used: int = 0

    def available(self, level: int) -> int:
        return self.max_slots.get(level, 0) - self.used_slots.get(level, 0)

    def use(self, level: int) -> bool:
        if self.available(level) > 0:
            self.used_slots[level] += 1
            return True
        return False

    def restore_all(self):
        self.used_slots = {i: 0 for i in range(1, 10)}
        self.pact_slots_used = 0


@dataclass
class ResourceTracker:
    """Tracks any limited-use resource: Rage, Ki, Bardic Inspiration, etc."""
    name: str
    max_uses: int
    current_uses: int
    restore_on: RestoreOn
    trait_id: str = ""


@dataclass
class InventoryItem:
    equipment_id: str
    quantity: int = 1
    equipped: bool = False
    attuned: bool = False
    notes: str = ""


@dataclass
class DeathSaves:
    successes: int = 0
    failures: int = 0
    stable: bool = False


@dataclass
class Conditions:
    """Active conditions per 2024 rules."""
    blinded:       bool = False
    charmed:       bool = False
    deafened:      bool = False
    exhaustion:    int  = 0      # 2024: levels 1-6
    frightened:    bool = False
    grappled:      bool = False
    incapacitated: bool = False
    invisible:     bool = False
    paralyzed:     bool = False
    petrified:     bool = False
    poisoned:      bool = False
    prone:         bool = False
    restrained:    bool = False
    stunned:       bool = False
    unconscious:   bool = False


@dataclass
class Character:
    """
    Top-level character state. This is what gets saved to JSON.

    Content references (class_id, species_id, etc.) are string IDs resolved
    at runtime through ContentRegistry — keeps saves small and portable.
    """
    id: str
    name: str
    player_name: str = ""
    alignment: str = "true neutral"
    backstory: str = ""
    appearance: str = ""
    notes: str = ""

    species_id: str = ""
    background_id: str = ""
    classes: list = field(default_factory=list)  # list[ClassLevel]

    ability_scores: AbilityScores = field(default_factory=AbilityScores)
    skills: dict = field(default_factory=dict)   # {str: SkillEntry}
    saving_throw_proficiencies: list = field(default_factory=list)  # list[AbilityScore]

    hp_max: int = 0
    hp_current: int = 0
    hp_temp: int = 0
    death_saves: DeathSaves = field(default_factory=DeathSaves)

    armor_class: int = 10
    initiative_bonus: int = 0
    speed: int = 30
    inspiration: bool = False

    extra_language_ids: list = field(default_factory=list)
    extra_tool_proficiencies: list = field(default_factory=list)

    spell_slots: SpellSlots = field(default_factory=SpellSlots)
    known_spells: list = field(default_factory=list)
    prepared_spells: list = field(default_factory=list)
    cantrips: list = field(default_factory=list)

    inventory: list = field(default_factory=list)   # list[InventoryItem]
    gold: float = 0.0
    resources: list = field(default_factory=list)   # list[ResourceTracker]

    conditions: Conditions = field(default_factory=Conditions)
    feat_ids: list = field(default_factory=list)

    # ---------- Computed properties ----------

    @property
    def total_level(self) -> int:
        return sum(c.level for c in self.classes)

    @property
    def proficiency_bonus(self) -> int:
        return max(2, (self.total_level - 1) // 4 + 2)

    def ability_modifier(self, ability: AbilityScore) -> int:
        return self.ability_scores.modifier(ability)

    def skill_bonus(self, skill_name: str) -> int:
        entry = self.skills.get(skill_name)
        if not entry:
            return 0
        ability_mod = self.ability_modifier(entry.governing_ability)
        prof = self.proficiency_bonus
        match entry.proficiency:
            case ProficiencyLevel.NONE:       return ability_mod
            case ProficiencyLevel.HALF:       return ability_mod + prof // 2
            case ProficiencyLevel.PROFICIENT: return ability_mod + prof
            case ProficiencyLevel.EXPERT:     return ability_mod + prof * 2
        return ability_mod

    def saving_throw_bonus(self, ability: AbilityScore) -> int:
        mod = self.ability_modifier(ability)
        if ability in self.saving_throw_proficiencies:
            return mod + self.proficiency_bonus
        return mod

    def passive_perception(self) -> int:
        return 10 + self.skill_bonus("perception")

    # ---------- Serialisation ----------

    def to_dict(self) -> dict:
        import dataclasses
        def _convert(obj):
            if isinstance(obj, Enum):
                return obj.value
            if dataclasses.is_dataclass(obj):
                return {k: _convert(v) for k, v in dataclasses.asdict(obj).items()}
            if isinstance(obj, list):
                return [_convert(i) for i in obj]
            if isinstance(obj, dict):
                return {k: _convert(v) for k, v in obj.items()}
            return obj
        return _convert(self)

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    @classmethod
    def from_dict(cls, data: dict) -> "Character":
        data = dict(data)
        if "ability_scores" in data:
            data["ability_scores"] = AbilityScores(**data["ability_scores"])
        if "death_saves" in data:
            data["death_saves"] = DeathSaves(**data["death_saves"])
        if "conditions" in data:
            data["conditions"] = Conditions(**data["conditions"])
        if "spell_slots" in data:
            ss = data["spell_slots"]
            data["spell_slots"] = SpellSlots(
                max_slots={int(k): v for k, v in ss.get("max_slots", {}).items()},
                used_slots={int(k): v for k, v in ss.get("used_slots", {}).items()},
                pact_slot_level=ss.get("pact_slot_level", 0),
                pact_slots_max=ss.get("pact_slots_max", 0),
                pact_slots_used=ss.get("pact_slots_used", 0),
            )
        if "classes" in data:
            data["classes"] = [ClassLevel(**c) for c in data["classes"]]
        if "saving_throw_proficiencies" in data:
            data["saving_throw_proficiencies"] = [
                AbilityScore(a) for a in data["saving_throw_proficiencies"]
            ]
        if "skills" in data:
            data["skills"] = {
                k: SkillEntry(
                    name=v["name"],
                    governing_ability=AbilityScore(v["governing_ability"]),
                    proficiency=ProficiencyLevel(v.get("proficiency", "none")),
                )
                for k, v in data["skills"].items()
            }
        if "resources" in data:
            data["resources"] = [
                ResourceTracker(
                    name=r["name"], max_uses=r["max_uses"],
                    current_uses=r["current_uses"],
                    restore_on=RestoreOn(r["restore_on"]),
                    trait_id=r.get("trait_id", ""),
                )
                for r in data["resources"]
            ]
        if "inventory" in data:
            data["inventory"] = [InventoryItem(**i) for i in data["inventory"]]
        return cls(**data)

    @classmethod
    def from_json(cls, json_str: str) -> "Character":
        return cls.from_dict(json.loads(json_str))


# ---------------------------------------------------------------------------
# Content Registry
# ---------------------------------------------------------------------------

class ContentRegistry:
    """
    Central store for all rule content.

    Loading order:
      1. Official 2024 content (hardcoded or bundled JSON)
      2. JSON files from your homebrew/ folder

    Homebrew overrides official content if IDs clash — useful for errata.

    Expected homebrew folder structure:
      homebrew/
        traits.json
        subclasses.json
        species.json
        backgrounds.json
        feats.json
        spells.json
    """

    def __init__(self):
        self.classes:     dict = {}
        self.subclasses:  dict = {}
        self.species:     dict = {}
        self.backgrounds: dict = {}
        self.feats:       dict = {}
        self.spells:      dict = {}
        self.traits:      dict = {}
        self.equipment:   dict = {}

    def register_subclass(self, sc: Subclass):    self.subclasses[sc.id] = sc
    def register_species(self, sp: Species):       self.species[sp.id] = sp
    def register_background(self, bg: Background): self.backgrounds[bg.id] = bg
    def register_feat(self, feat: Feat):           self.feats[feat.id] = feat
    def register_spell(self, spell: Spell):        self.spells[spell.id] = spell
    def register_trait(self, trait: Trait):        self.traits[trait.id] = trait

    def load_homebrew_folder(self, folder_path: str):
        """Scan a folder for JSON homebrew files and load all found."""
        loaders = {
            "traits.json":      self._load_traits,
            "subclasses.json":  self._load_subclasses,
            "species.json":     self._load_species,
            "backgrounds.json": self._load_backgrounds,
            "feats.json":       self._load_feats,
            "spells.json":      self._load_spells,
        }
        for filename, loader in loaders.items():
            path = os.path.join(folder_path, filename)
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    loader(json.load(f))

    def _load_traits(self, data: list):
        for d in data:
            self.register_trait(Trait(
                id=d["id"], name=d["name"], description=d["description"],
                source=d.get("source", "homebrew"), homebrew=d.get("homebrew", True),
                mechanics=d.get("mechanics", {}),
            ))

    def _load_subclasses(self, data: list):
        for d in data:
            features = {}
            for level_str, trait_list in d.get("features", {}).items():
                parsed = []
                for t in trait_list:
                    if isinstance(t, str):
                        parsed.append(self.traits.get(t) or Trait(id=t, name=t, description="", source="homebrew"))
                    else:
                        parsed.append(Trait(
                            id=t["id"], name=t["name"], description=t.get("description", ""),
                            source=d.get("source", "homebrew"), homebrew=d.get("homebrew", True),
                            mechanics=t.get("mechanics", {}),
                        ))
                features[int(level_str)] = parsed
            self.register_subclass(Subclass(
                id=d["id"], name=d["name"], parent_class_id=d["parent_class_id"],
                description=d.get("description", ""), source=d.get("source", "homebrew"),
                homebrew=d.get("homebrew", True), features=features,
                spellcasting_type=SpellcastingType(d.get("spellcasting_type", "none")),
                subclass_spell_list=d.get("subclass_spell_list", []),
            ))

    def _load_species(self, data: list):
        for d in data:
            traits = [
                self.traits.get(t_id) or Trait(id=t_id, name=t_id, description="", source="homebrew")
                for t_id in d.get("trait_ids", [])
            ]
            self.register_species(Species(
                id=d["id"], name=d["name"], description=d.get("description", ""),
                source=d.get("source", "homebrew"), homebrew=d.get("homebrew", True),
                size=d.get("size", "medium"), base_speed=d.get("base_speed", 30),
                traits=traits, languages=d.get("languages", []),
            ))

    def _load_backgrounds(self, data: list):
        for d in data:
            self.register_background(Background(
                id=d["id"], name=d["name"], description=d.get("description", ""),
                source=d.get("source", "homebrew"), homebrew=d.get("homebrew", True),
                skill_proficiencies=d.get("skill_proficiencies", []),
                tool_proficiency=d.get("tool_proficiency"),
                languages=d.get("languages", 1),
                origin_feat_id=d.get("origin_feat_id"),
                starting_equipment=d.get("starting_equipment", []),
            ))

    def _load_feats(self, data: list):
        for d in data:
            self.register_feat(Feat(
                id=d["id"], name=d["name"], description=d["description"],
                source=d.get("source", "homebrew"), homebrew=d.get("homebrew", True),
                category=d.get("category", "general"),
                prerequisites=d.get("prerequisites", []),
                repeatable=d.get("repeatable", False),
                mechanics=d.get("mechanics", {}),
            ))

    def _load_spells(self, data: list):
        for d in data:
            self.register_spell(Spell(
                id=d["id"], name=d["name"], level=d["level"], school=d["school"],
                casting_time=d["casting_time"], range=d["range"],
                components=d["components"], duration=d["duration"],
                description=d["description"], source=d.get("source", "homebrew"),
                homebrew=d.get("homebrew", True), classes=d.get("classes", []),
                ritual=d.get("ritual", False), concentration=d.get("concentration", False),
                upcast_description=d.get("upcast_description"),
            ))

    def get_subclasses_for_class(self, class_id: str) -> list:
        return [sc for sc in self.subclasses.values() if sc.parent_class_id == class_id]


# ---------------------------------------------------------------------------
# Example homebrew JSON (copy to homebrew/subclasses.json)
# ---------------------------------------------------------------------------

EXAMPLE_HOMEBREW_SUBCLASS_JSON = """
[
  {
    "id": "storm_herald",
    "name": "Path of the Storm Herald",
    "parent_class_id": "barbarian",
    "description": "Barbarians who channel primal storms.",
    "source": "XGtE",
    "homebrew": false,
    "features": {
      "3": [
        {
          "id": "storm_aura",
          "name": "Storm Aura",
          "description": "While raging, you emanate a 10-foot aura of storm energy.",
          "mechanics": {"type": "aura", "radius": 10, "trigger": "raging"}
        }
      ],
      "6": [
        {
          "id": "storm_soul",
          "name": "Storm Soul",
          "description": "Resistance to a damage type based on your chosen storm.",
          "mechanics": {"type": "resistance", "damage_type": "varies"}
        }
      ]
    }
  },
  {
    "id": "void_blade",
    "name": "Oath of the Void Blade",
    "parent_class_id": "paladin",
    "description": "A paladin sworn to seal rifts between planes.",
    "source": "homebrew",
    "homebrew": true,
    "subclass_spell_list": ["blink", "misty_step", "plane_shift"],
    "features": {
      "3": [
        {
          "id": "void_smite",
          "name": "Void Smite",
          "description": "Your Divine Smite deals force damage instead of radiant.",
          "mechanics": {"type": "damage_override", "from": "radiant", "to": "force"}
        }
      ],
      "7": [
        {
          "id": "planar_ward",
          "name": "Planar Ward",
          "description": "Allies within 10ft have advantage on saves vs. teleportation.",
          "mechanics": {"type": "aura", "radius": 10, "effect": "advantage_teleport_saves"}
        }
      ]
    }
  }
]
"""

EXAMPLE_HOMEBREW_BACKGROUND_JSON = """
[
  {
    "id": "planar_refugee",
    "name": "Planar Refugee",
    "description": "Displaced from your home plane by a catastrophic event.",
    "source": "homebrew",
    "homebrew": true,
    "skill_proficiencies": ["arcana", "survival"],
    "tool_proficiency": "cartographers_tools",
    "languages": 1,
    "origin_feat_id": "magic_initiate",
    "starting_equipment": ["traveler's clothes", "50gp", "planar map fragment"]
  }
]
"""


# ---------------------------------------------------------------------------
# Quick demo
# ---------------------------------------------------------------------------

def create_sample_character() -> Character:
    import uuid
    return Character(
        id=str(uuid.uuid4()),
        name="Seraphina Dawnblade",
        player_name="Alex",
        alignment="lawful good",
        species_id="aasimar",
        background_id="soldier",
        classes=[
            ClassLevel(
                class_id="paladin", level=5,
                subclass_id="oath_of_devotion",
                level_choices={4: {"type": "feat", "feat_id": "war_caster"}},
            )
        ],
        ability_scores=AbilityScores(
            strength=18, dexterity=10, constitution=14,
            intelligence=10, wisdom=12, charisma=16,
        ),
        skills={
            "athletics":  SkillEntry("Athletics",  AbilityScore.STR, ProficiencyLevel.PROFICIENT),
            "insight":    SkillEntry("Insight",    AbilityScore.WIS, ProficiencyLevel.PROFICIENT),
            "perception": SkillEntry("Perception", AbilityScore.WIS, ProficiencyLevel.NONE),
            "religion":   SkillEntry("Religion",   AbilityScore.INT, ProficiencyLevel.PROFICIENT),
            "persuasion": SkillEntry("Persuasion", AbilityScore.CHA, ProficiencyLevel.PROFICIENT),
        },
        saving_throw_proficiencies=[AbilityScore.WIS, AbilityScore.CHA],
        hp_max=52, hp_current=52,
        armor_class=18, speed=30,
        spell_slots=SpellSlots(
            max_slots={1: 4, 2: 2, 3: 0, 4: 0, 5: 0, 6: 0, 7: 0, 8: 0, 9: 0},
            used_slots={i: 0 for i in range(1, 10)},
        ),
        prepared_spells=["cure_wounds", "divine_favor", "bless", "shield_of_faith"],
        resources=[
            ResourceTracker("Lay on Hands", 25, 25, RestoreOn.LONG, "lay_on_hands"),
            ResourceTracker("Channel Divinity", 2, 2, RestoreOn.SHORT, "channel_divinity"),
        ],
        gold=150.0,
    )


if __name__ == "__main__":
    char = create_sample_character()
    print(f"Character: {char.name}")
    print(f"Level: {char.total_level}  |  Proficiency: +{char.proficiency_bonus}")
    print(f"STR mod: {char.ability_modifier(AbilityScore.STR):+}")
    print(f"Athletics: {char.skill_bonus('athletics'):+}")
    print(f"CHA save: {char.saving_throw_bonus(AbilityScore.CHA):+}")
    print(f"Passive Perception: {char.passive_perception()}")

    json_str = char.to_json()
    reloaded = Character.from_json(json_str)
    print(f"\nReloaded from JSON: {reloaded.name} (level {reloaded.total_level})")

    registry = ContentRegistry()
    registry._load_subclasses(json.loads(EXAMPLE_HOMEBREW_SUBCLASS_JSON))
    registry._load_backgrounds(json.loads(EXAMPLE_HOMEBREW_BACKGROUND_JSON))

    paladin_subs = registry.get_subclasses_for_class("paladin")
    print(f"\nPaladin subclasses: {[sc.name for sc in paladin_subs]}")
    print(f"Homebrew backgrounds: {[bg.name for bg in registry.backgrounds.values()]}")
