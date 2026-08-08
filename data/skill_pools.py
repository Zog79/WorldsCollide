"""
Portage de la logique de ranking/groupement de sorts de Beyond Chaos
(BeyondChaos/skillrandomizer.py : SpellBlock.rank(), get_spellsets())

Cette classe n'ajoute pas de nouveaux champs en ROM : elle interprète les
mêmes octets bruts que data.ability_data.AbilityData / data.spell.Spell,
avec les mêmes masques de bits que BC, pour que le classement (rank) et
les regroupements thématiques (Fire, Heal, Curse, Esper, Limit, ...)
donnent des résultats équivalents à ceux de Beyond Chaos.
"""

import random
from data.spell_names import name_id
from memory.space import Bank, Write
import instruction.asm as asm
import instruction.c2 as c2

# Routines vanilla du moteur de combat (banque C2), identifiées à partir du
# bytecode de Beyond Chaos (skillrandomizer.SpellSub / RandomSpellSub).
# Ni WC ni BC ne les modifient (vérifié sur l'archive complète de WC) : elles
# restent valides telles quelles. Toujours en offset local à la banque C2.
# TODO: candidat à cataloguer proprement dans instruction/c2.py à terme.
_TARGET_SETUP_1 = 0x19C1   # JSR - prépare la sélection de cible (1/2)
_TARGET_SETUP_2 = 0x2951   # JSR - prépare la sélection de cible (2/2)
_CAST_DISPATCHER = 0x175F  # JMP - dispatcher générique d'exécution de capacité
                            # (point d'entrée partagé par Lore/Magitek en vanilla)

# Adresses RAM utilisées par le dispatcher (mêmes conventions que BC) :
# $B6 = id de la capacité à lancer, $B5 = type (0x02 = capacité), $B8/$B9 = cibles


def write_spell_sub(spell_id, description="skill_pools fixed spell sub"):
    """Porte SpellSub de BC : remplace une commande par un unique sort fixe.
    Retourne l'adresse (locale banque C2) du code généré, à utiliser pour
    patcher l'entrée de la jump table de la commande (commandcodes.txt)."""
    src = [
        asm.LDA(spell_id, asm.IMM8),
        asm.STA(0xB6, asm.DIR),
        asm.LDA(0x02, asm.IMM8),
        asm.STA(0xB5, asm.DIR),
        asm.JMP(_CAST_DISPATCHER, asm.ABS),
    ]
    space = Write(Bank.C2, src, description)
    return space.start_address


def rename_command(command_name, new_name):
    """Porte CommandBlock.newname() de BC : change le nom affiché dans le
    menu de combat (ex. remplace 'Blitz' par 'Cure' quand la commande a été
    redirigée vers ce sort). 7 caractères max, comme BC."""
    from constants.command_codes import command_codes
    from memory.space import Reserve
    import data.text as text

    code = command_codes[command_name]
    name = new_name.strip().replace(' ', '').replace('-', '')[:7]
    values = text.get_bytes(name, text.TEXT2)
    values.extend([0xff] * (7 - len(values)))
    space = Reserve(code.textptr, code.textptr + 6,
                    f"skill_pools: renommage {command_name} -> {name}")
    space.write(values)


def unset_menu(command_name):
    """Porte CommandBlock.unsetmenu() de BC : retire l'icône de sous-menu
    devenue obsolète (liste de danses/techniques/rages...) pour une
    commande redirigée vers un sort/pool généré."""
    from constants.command_codes import command_codes
    from memory.space import Reserve

    code = command_codes[command_name]
    space = Reserve(code.menu, code.menu + 1,
                    f"skill_pools: désactive sous-menu {command_name}")
    space.write(0x95, 0x77)


def set_command_skill(command_name, code_address):
    """Porte CommandBlock.setpointer() de BC : redirige l'exécution d'une
    commande (Fight/Rage/Lore/SwdTech/Blitz/Dance/...) vers le bytecode
    généré par write_spell_sub / write_random_spell_sub.

    command_name : une des clefs de constants.command_codes.command_codes
                   (alignées sur constants.commands.id_name).
    code_address : adresse locale banque C2 retournée par write_spell_sub
                   ou write_random_spell_sub."""
    from constants.command_codes import command_codes
    from memory.space import Reserve

    code = command_codes[command_name]
    local_offset = code_address & 0xFFFF
    space = Reserve(code.pointer, code.pointer + 1,
                    f"skill_pools: redirection commande {command_name}")
    space.write(
        (local_offset & 0xFF),
        (local_offset >> 8) & 0xFF,
    )


# --- Commandes toujours protégées, où qu'elles se trouvent -----------------
# Jamais réassignées, jamais réécrites -- gardent leur comportement vanilla
# exact sur le personnage qui les a déjà en vanilla.
# - Possess : commande figée d'Umaro (Umaro est de toute façon exclu du
#   système entier, voir SkillPools.mod()).
# - Leap : PREUVE TECHNIQUE (data/rages.py "rages add leap command if on
#   veldt", label EMPTY_COMMAND_SLOT à 0x25434) -- le jeu vanilla
#   ajoute/retire DYNAMIQUEMENT ce slot selon que le personnage est ou non
#   sur le Veldt, et le remet à vide sinon, quel que soit ce qu'on y écrit
#   statiquement. Aucun contournement possible côté skill_pools.
# - Row/Def/Mimic/Summon : WC lui-même les exclut de sa fonctionnalité
#   native de randomisation de commandes (constants.commands.EXCLUDE_COMMANDS).
PROTECTED_ALWAYS = ["Possess", "Leap", "Row", "Def", "Mimic", "Summon"]

# --- Commandes "vanilla nommées" ---------------------------------------
# Choix explicite pour un slot précis (jamais piochée au hasard dans le
# pool aléatoire) : garde toujours son vrai comportement.
# Fight -> toujours slot 1. Item -> tirage explicite pour le slot 4.
# Magic n'est PLUS assignée explicitement par nous : le slot 2 est
# laissé à la logique déjà existante de WC (native, ex. -com), voir
# SkillPools.mod() -- évite de réintroduire "Magic" nous-mêmes, cause
# probable de plusieurs cas de slot vide observés (Locke, Terra, Edgar).
VANILLA_NAMED = ["Fight", "Item"]

# --- Pool aléatoire ("notre système") -----------------------------------
# Chaque commande ci-dessous reçoit, une fois pour la seed, un sort
# aléatoire fixe (bytecode + jump table + nom affiché + ciblage). Comme ces
# commandes sont ENTIÈREMENT redirigées vers un sort généré, leur éventuelle
# dépendance vanilla à une liste de techniques déjà apprises (Blitz, Lore,
# Dance, SwdTech, Rage, X Magic...) ne s'applique plus : le jeu n'interroge
# plus jamais cette liste, il exécute directement le sort assigné. C'est ce
# qui rend ces commandes sûres à inclure ici, contrairement à Leap (dont le
# blocage est indépendant du contenu -- voir PROTECTED_ALWAYS).
CARRIER_POOL = ["Morph", "Revert", "Steal", "Capture", "SwdTech", "Throw",
                "Tools", "Blitz", "Runic", "Lore", "Sketch", "Control",
                "Slot", "Rage", "Dance", "Jump", "X Magic", "GP Rain",
                "Health", "Shock", "MagiTek"]

NEVER_REPLACE = PROTECTED_ALWAYS + VANILLA_NAMED + CARRIER_POOL


def write_command_properties(command_name, properties, targeting):
    """Porte CommandBlock.write_properties() de BC : propriétés (usable en
    tant qu'imp/mimable/gogo) et bits de ciblage d'une commande. Nécessaire
    pour que le curseur de sélection de cible corresponde au VRAI sort
    assigné plutôt qu'à celui de la commande d'origine (ex. Blitz)."""
    from constants.commands import name_id
    from memory.space import Reserve

    numeric_id = name_id[command_name]
    proppointer = 0xFFE00 + numeric_id * 2
    space = Reserve(proppointer, proppointer + 1,
                    f"skill_pools: propriétés/ciblage {command_name}")
    space.write(properties, targeting)


def write_magic_known_spell_fix(args, magic_character_indices, spell_name="Cure"):
    """Garantit qu'un personnage ayant reçu Magic via notre système connaît
    au moins un sort, pour satisfaire le check vanilla (banque C3, adresse
    locale $0D2B, "check to see if character knows magic") qui remplace
    silencieusement la commande Magic par $FF ("aucune commande") dans le
    menu de combat si le personnage ne connaît aucun sort -- exactement
    la cause confirmée (par désassemblage vanilla) des slots vides observés.

    N'écrit RIEN si magic_character_indices est vide (aucun personnage
    concerné cette seed) -- ne touche alors absolument rien.

    Point d'accroche : identique à settings/initial_spells.py (utilisé par
    les flags natifs -scan_all/-warp_all), le seul endroit vanilla qui
    initialise les sorts connus au tout début de partie, avant que le
    joueur puisse accéder à un menu. Comme ce point (0x0bdcc-0x0bdd6)
    n'est réclamé qu'une fois, et que skill_pools.mod() (dans Data.mod())
    s'exécute AVANT settings.Settings()/InitialSpells() dans wc.py, cette
    fonction reproduit fidèlement leur comportement (-scan_all/-warp_all)
    en plus du nôtre pour rester compatible si ces flags sont combinés à
    -rsk -- sans quoi InitialSpells lèverait un conflit de réservation."""
    if not magic_character_indices:
        return  # aucun personnage concerné, ne touche à rien

    from data.spells import Spells
    from data.characters import Characters
    from data.spell_names import name_id
    from memory.space import Bank, Reserve, Write, Read

    learned_spells_start = 0x1a6e
    spell_id = name_id[spell_name]

    # réplique fidèle de settings/initial_spells.py (-scan_all/-warp_all)
    # pour rester compatible si ces flags sont actifs en même temps
    all_characters_spells = []
    if getattr(args, "scan_all", False):
        all_characters_spells.append(name_id["Scan"])
    if getattr(args, "warp_all", False):
        all_characters_spells.append(name_id["Warp"])

    src = [
        Read(0x0bdcc, 0x0bdd6),  # comportement vanilla original (zero out), inchangé
        asm.PHY(),
    ]

    if all_characters_spells:
        learner_count = Characters.CHARACTER_COUNT - 2  # pas gogo/umaro
        last_offset = Spells.SPELL_COUNT * learner_count
        src += [
            asm.LDX(0x00, asm.DIR),
            "ALL_CHARACTERS_LOOP_START",
        ]
        for all_spell_id in all_characters_spells:
            src += [
                asm.A16(),
                asm.TXA(),
                asm.CLC(),
                asm.ADC(all_spell_id, asm.IMM16),
                asm.TAY(),
                asm.A8(),
                asm.LDA(0xff, asm.IMM8),
                asm.STA(learned_spells_start, asm.ABS_Y),
            ]
        src += [
            asm.A16(),
            asm.TXA(),
            asm.CLC(),
            asm.ADC(Spells.SPELL_COUNT, asm.IMM16),
            asm.TAX(),
            asm.A8(),
            asm.CPX(last_offset, asm.IMM16),
            asm.BLT("ALL_CHARACTERS_LOOP_START"),
        ]

    # notre ajout : un sort garanti, uniquement pour les personnages
    # précis ayant reçu Magic via notre système -- adresse fixe connue à
    # l'avance (pas de boucle nécessaire), aucun autre personnage touché
    for character_index in magic_character_indices:
        address = learned_spells_start + Spells.SPELL_COUNT * character_index + spell_id
        src += [
            asm.LDA(0xff, asm.IMM8),
            asm.STA(address, asm.ABS),
        ]

    src += [
        asm.PLY(),
        asm.TDC(),
        asm.RTL(),
    ]
    space = Write(Bank.F0, src, "skill_pools: sort garanti pour Magic")
    fix_snes = space.start_address_snes

    space = Reserve(0x0bdcc, 0x0bdd6,
                    "skill_pools: init sorts (+ sort garanti Magic)", asm.NOP())
    space.write(
        asm.JSL(fix_snes),
    )


class SkillPools:
    """Orchestrateur par personnage et par slot positionnel :

    - slot 1 : toujours Fight (100%), sans exception.
    - slot 2 : INTOUCHÉ -- laissé à la logique déjà existante de WC
      (native, ex. -com), qui fonctionne déjà correctement. On ne fait
      que LIRE son contenu final (pour éviter les doublons), jamais
      l'écrire.
    - slot 3 : 100% commande aléatoire du pool ("notre système",
      CARRIER_POOL), jamais une commande vanilla, jamais vide, jamais
      un doublon avec le slot 2.
    - slot 4 : 50% Item (vrai comportement) / 50% commande aléatoire du
      pool, jamais un doublon avec les slots 2/3.

    Umaro reste 100% vanilla (exclu). Les commandes de PROTECTED_ALWAYS
    (Possess, Leap, Row, Def, Mimic, Summon) restent protégées où
    qu'elles se trouvent déjà chez un personnage, quel que soit le slot
    positionnel : si un slot contient déjà l'une d'elles, la règle
    positionnelle ne s'applique pas à ce slot et son contenu est laissé
    identique."""

    def __init__(self, rom, args, spells_data, characters_data):
        self.rom = rom
        self.args = args
        self.spells_data = spells_data
        self.characters_data = characters_data
        self.replacements = {}       # command_name -> nom du sort assigné (commandes du pool)
        self.character_layouts = {}  # nom du personnage -> liste des 4 commandes finales
        self.diagnostics = {}        # command_name -> détails techniques (adresse, ciblage, id...)
        self.character_raw_bytes = {}  # nom du personnage -> les 4 octets bruts réellement écrits

    def mod(self):
        if not getattr(self.args, "randomize_skills", False):
            return

        from constants.commands import id_name, name_id
        from data.characters import Characters

        skills = get_skills(self.spells_data, rom=self.rom)

        # 0. Le slot 2 est laissé à la logique déjà existante de WC (native
        #    ou -com), qui a déjà tourné à ce stade (Characters.mod(), donc
        #    -com, s'exécute avant skill_pools.mod()). Problème : notre
        #    CARRIER_POOL et le pool natif de WC (RANDOM_POSSIBLE_COMMANDS,
        #    constants/commands.py) se recoupent presque entièrement --
        #    Tools/Blitz/SwdTech/Lore/Dance/etc apparaissent dans les deux.
        #    Si on redirige globalement "Tools" vers un sort, un personnage
        #    qui a "Tools" au slot 2 via -com voit quand même NOTRE sort, pas
        #    le vrai Tools -- d'où l'impression que le slot 2 "suit notre
        #    système". Fix : on relève dynamiquement, pour cette seed,
        #    tout ce que WC a déjà placé au slot 2 de N'IMPORTE QUEL
        #    personnage, et on exclut ces noms précis de notre pool -- ces
        #    commandes gardent alors leur vrai comportement vanilla partout.
        reserved_for_slot2 = set()
        for index, character in enumerate(self.characters_data.playable):
            if index == Characters.UMARO:
                continue
            slot2_name = id_name.get(character.commands[1])
            if slot2_name:
                reserved_for_slot2.add(slot2_name)

        active_carrier_pool = [c for c in CARRIER_POOL if c not in reserved_for_slot2]
        if not active_carrier_pool:
            # cas extrême (peu probable) : -com a occupé tout le pool
            active_carrier_pool = list(CARRIER_POOL)

        # 1. chaque commande du pool ACTIF reçoit, une fois pour la seed, un
        #    sort aléatoire fixe avec ciblage corrigé
        for command_name in active_carrier_pool:
            skill = random.choice(skills)
            addr = write_spell_sub(skill.id, f"skill_pools {command_name} -> {skill.name}")
            set_command_skill(command_name, addr)
            rename_command(command_name, skill.name)
            unset_menu(command_name)

            raw_targeting = skill.targeting
            targeting = raw_targeting & (0xFF ^ 0x10)  # jamais l'autotarget
            fallback_used = False
            if targeting == 0:
                targeting = 0x40  # target_enemy_default
                fallback_used = True
            write_command_properties(command_name, 3, targeting)

            self.replacements[command_name] = skill.name
            self.diagnostics[command_name] = {
                "skill_name": skill.name,
                "skill_id": skill.id,
                "code_address_local": hex(addr),
                "code_address_pc_bank_c2": hex(0x20000 + (addr & 0xFFFF)),
                "command_numeric_id": name_id[command_name],
                "raw_targeting": hex(raw_targeting),
                "final_targeting": hex(targeting),
                "fallback_used": fallback_used,
                "properties_pointer": hex(0xFFE00 + name_id[command_name] * 2),
            }

        vanilla_chance = getattr(self.args, "randomize_skills_vanilla_chance", 0.5)
        fight_magic_chance = getattr(self.args, "randomize_skills_magic_chance", 0.5)

        # commandes de NOTRE système déjà données à un personnage cette
        # seed -- on les évite en priorité pour les autres personnages,
        # tant que le pool actif le permet, pour maximiser la diversité
        # (ne s'applique jamais à Fight/Magic/Item/vanilla WC/protégées)
        used_globally = set()

        # personnages ayant reçu Magic via notre système cette seed -- sert
        # uniquement à write_magic_known_spell_fix() ci-dessous, aucune
        # autre logique n'en dépend
        magic_character_indices = []

        # 2. chaque personnage reçoit son layout, slot par slot
        for index, character in enumerate(self.characters_data.playable):
            if index == Characters.UMARO:
                self.character_layouts[character.name] = \
                    [id_name.get(c, "?") for c in character.commands]
                continue

            used = set()
            layout = [None] * len(character.commands)

            for slot in range(len(character.commands)):
                current_name = id_name.get(character.commands[slot])

                if slot == 1:
                    # slot 2 : jamais touché -- on lit juste le résultat
                    # déjà décidé par WC (native/-com) pour éviter un
                    # doublon avec les slots 3/4.
                    layout[slot] = current_name
                    used.add(current_name)
                    continue

                if current_name in PROTECTED_ALWAYS:
                    layout[slot] = current_name
                    used.add(current_name)
                    continue

                if slot == 0:
                    # 50% Fight / 50% Magic (jamais Magic si déjà présente
                    # au slot 2 par ailleurs, cas extrêmement rare -- repli
                    # sur Fight pour éviter tout doublon)
                    if random.random() < fight_magic_chance and "Magic" not in used:
                        chosen = "Magic"
                        magic_character_indices.append(index)
                    else:
                        chosen = "Fight"
                elif slot == 2:
                    # 100% aléatoire, jamais vanilla, jamais vide, en
                    # priorité une commande pas encore utilisée par un
                    # autre personnage cette seed
                    choices = [c for c in active_carrier_pool if c not in used and c not in used_globally] \
                        or [c for c in active_carrier_pool if c not in used] \
                        or list(active_carrier_pool)
                    chosen = random.choice(choices)
                else:
                    # slot 3 (Item 50%)
                    if random.random() < vanilla_chance and "Item" not in used:
                        chosen = "Item"
                    else:
                        choices = [c for c in active_carrier_pool if c not in used and c not in used_globally] \
                            or [c for c in active_carrier_pool if c not in used] \
                            or list(active_carrier_pool)
                        chosen = random.choice(choices)

                character.commands[slot] = name_id[chosen]
                used.add(chosen)
                if chosen in active_carrier_pool:
                    used_globally.add(chosen)
                layout[slot] = chosen

            self.character_layouts[character.name] = layout
            self.character_raw_bytes[character.name] = list(character.commands)

        # 3. garantit qu'un personnage ayant reçu Magic connaît au moins un
        #    sort (voir write_magic_known_spell_fix pour le détail) -- ne
        #    fait RIEN si aucun personnage n'a reçu Magic cette seed
        self.magic_character_indices = magic_character_indices
        write_magic_known_spell_fix(self.args, magic_character_indices)

    def write(self):
        if self.args.spoiler_log:
            self.log()

    def log(self):
        from log import section

        if not self.replacements and not self.character_layouts:
            return

        lcolumn = []
        for character_name, layout in self.character_layouts.items():
            display = []
            for command_name in layout:
                if command_name in self.replacements:
                    display.append(self.replacements[command_name])
                else:
                    display.append(command_name)
            lcolumn.append(f"{character_name:<8} {', '.join(display)}")

        section("Skill Pools", lcolumn, [])

        # --- DIAGNOSTIC DÉTAILLÉ (utile en cas de nouveau signalement) ---
        diag_lines = []
        diag_lines.append("--- Commandes porteuses (diagnostic) ---")
        for command_name, info in self.diagnostics.items():
            diag_lines.append(
                f"{command_name:<10} id={info['command_numeric_id']:<3} "
                f"skill={info['skill_name']:<10} skill_id={info['skill_id']} "
                f"addr_local={info['code_address_local']} "
                f"addr_bankC2={info['code_address_pc_bank_c2']} "
                f"targeting_brut={info['raw_targeting']} "
                f"targeting_final={info['final_targeting']} "
                f"repli_utilisé={info['fallback_used']} "
                f"proppointer={info['properties_pointer']}"
            )
        diag_lines.append("--- Octets bruts par personnage (slot1..slot4) ---")
        for character_name, raw in self.character_raw_bytes.items():
            diag_lines.append(f"{character_name:<8} {raw}")

        section("Skill Pools Diagnostic", diag_lines, [])


class SkillProperties:
    """Enveloppe un objet Spell (ou tout AbilityData) de WC et expose les
    mêmes propriétés booléennes que SpellBlock de BC, calculées à partir
    des mêmes octets bruts (targets/elements/flags1-3/status1-4)."""

    def __init__(self, spell):
        self.spell = spell
        self.id = spell.id
        self.name = spell.get_name() if hasattr(spell, "get_name") else getattr(spell, "name", "?")

        targeting = spell.targets
        self.targeting = targeting
        self.target_random = bool(targeting & 0x80)
        self.target_enemy_default = bool(targeting & 0x40)
        self.target_group = bool(targeting & 0x20)
        self.target_auto = bool(targeting & 0x10)
        self.target_group_default = bool(targeting & 0x08)
        self.target_everyone = bool(targeting & 0x04)
        self.target_one_side_only = bool(targeting & 0x02)
        self.target_one = bool(targeting & 0x01)

        self.elements = spell.elements
        self.elemental = self.elements > 0

        effect1 = spell.flags1
        self.physical = bool(effect1 & 0x01)
        self.miss_if_death_prot = bool(effect1 & 0x02)
        self.target_dead = bool(effect1 & 0x04)
        self.invert_undead = bool(effect1 & 0x08)
        self.randomize_target = bool(effect1 & 0x10)
        self.ignore_defense = bool(effect1 & 0x20)
        self.no_split_damage = bool(effect1 & 0x40)
        self.abort_on_allies = bool(effect1 & 0x80)

        dmgtype = spell.flags2
        self.dmgtype = dmgtype
        self.outsidebattle = bool(dmgtype & 0x01)
        self.unreflectable = bool(dmgtype & 0x02)
        self.learnifcast = bool(dmgtype & 0x04)
        self.enablerunic = bool(dmgtype & 0x08)
        self.retargetdead = bool(dmgtype & 0x20)
        self.casterdies = bool(dmgtype & 0x40)
        self.concernsmp = bool(dmgtype & 0x80)

        effect2 = spell.flags3
        self.healing = bool(effect2 & 0x01)
        self.draining = bool(effect2 & 0x02)
        self.cure_status = bool(effect2 & 0x04)
        self.invert_status = bool(effect2 & 0x08)
        self.uses_stamina = bool(effect2 & 0x10)
        self.unblockable = bool(effect2 & 0x20)
        self.level_spell = bool(effect2 & 0x40)
        self.percentage = bool(effect2 & 0x80)

        self.mp = spell.mp
        self.power = spell.power
        self.accuracy = spell.accuracy

        statuses = [spell.status1, spell.status2, spell.status3, spell.status4]
        self.statuses = statuses
        self.death = bool(statuses[0] & 0x80)
        self.petrify = bool(statuses[0] & 0x40)
        self.condemned = bool(statuses[1] & 0x1)
        self.has_status = sum(bin(b).count("1") for b in statuses)

        self._rank = None

    def __hash__(self):
        return self.id

    def __eq__(self, other):
        return isinstance(other, SkillProperties) and self.id == other.id

    def __repr__(self):
        return self.name

    def rank(self):
        """Port fidèle de SpellBlock.rank() de Beyond Chaos."""
        if self._rank is not None:
            return self._rank

        if self.power >= 1 and not self.percentage and not self.draining:
            power = self.power
            baseline = power
        else:
            power = None
            baseline = 20

        if self.accuracy:
            baseline = baseline * 0.9

        if self.target_enemy_default or (self.target_everyone and not self.target_one_side_only):
            if power:
                if self.ignore_defense:
                    baseline = baseline * 2
                if self.elemental:
                    baseline = baseline * 0.75
                if self.no_split_damage:
                    baseline = baseline * 1.5
                if self.invert_undead:
                    baseline = baseline * 0.75
                if self.uses_stamina:
                    baseline = baseline * 0.75

            if self.power and self.draining:
                baseline = baseline * 2

            if self.physical:
                baseline = baseline * 0.3
            if self.unblockable:
                baseline = baseline * 1.25
            if self.has_status:
                baseline = baseline * 1.25

            if self.miss_if_death_prot:
                if self.death:
                    baseline = baseline * 3.5
                elif self.petrify:
                    baseline = baseline * 3
                elif self.condemned:
                    baseline = baseline * 1
                elif self.percentage:
                    baseline = baseline * 1
                else:
                    baseline = baseline * 2
            elif self.petrify and not power:
                baseline = baseline * 3
            elif self.petrify:
                baseline = baseline * 1.5
        else:
            if self.death:
                baseline = baseline * 0.1

        if self.healing or not self.target_enemy_default:
            baseline = baseline * 0.5
        if self.level_spell:
            baseline = baseline * 0.25

        self._rank = int(baseline)
        return self._rank


# IDs des techniques de Limite (Desperation Attacks), par nom -- identique à
# BC (is_desperation), traduit en IDs via spell_names.name_id de WC
LIMIT_NAMES = ["Sabre Soul", "Star Prism", "Mirager", "TigerBreak", "Back Blade",
               "Riot Blade", "RoyalShock", "Spin Edge", "X-Meteo", "Red Card",
               "MoogleRush", "ShadowFang"]


def get_skills(spells_data, rom=None):
    """Porte get_ranked_spells() de BC : lit la table d'abilities PARTAGÉE
    (sorts, invocations d'Esper, techniques SwdTech/Blitz, Lores, Rages,
    danses...) sur la quasi-totalité de sa plage (0x046ac0-0x0478bf, 256
    entrées identifiées par data.spell_names.id_name), au lieu de se
    limiter aux 54 sorts standards de data.spells.Spells. C'est ce vaste
    pool qui donne la diversité façon BC plutôt qu'un petit ensemble
    restreint -- exactement la même table que data.rages.Rages utilise
    déjà pour ses propres capacités.

    `rom` : nécessaire pour lire la plage étendue ; si omis, retombe sur
    les 54 entrées de spells_data.spells (comportement historique)."""
    if rom is None:
        return [SkillProperties(spell) for spell in spells_data.spells]

    from data.structures import DataArray
    from data.ability_data import AbilityData
    from data.spell_names import id_name

    ABILITY_DATA_START = 0x046ac0
    ABILITY_DATA_END = 0x0478bf  # 256 entrées, même plage que data.rages.Rages

    raw = DataArray(rom, ABILITY_DATA_START, ABILITY_DATA_END, AbilityData.DATA_SIZE)
    skills = []
    for i in range(len(raw)):
        name = id_name.get(i)
        if not name or name in ("Nothing", "??????????"):
            continue  # entrées placeholder/cassées (0xFE Lagomorph, 0xFF)
        ability = AbilityData(i, raw[i])
        ability.name = name
        skills.append(SkillProperties(ability))
    return skills


_wildskills = None


def get_spellsets(skills):
    """Port de get_spellsets() de Beyond Chaos. `skills` est une liste de
    SkillProperties (cf get_skills). Retourne un dict {clef: (description, [SkillProperties])}."""
    global _wildskills

    spellsets = {}
    limit_ids = [name_id[n] for n in LIMIT_NAMES if n in name_id]
    limit_skills = [s for s in skills if s.id in limit_ids]

    spellsets['Chaos'] = ('capacité (y compris cassée/glitchée)', list(skills))
    if _wildskills is None:
        _wildskills = random.sample(skills, min(8, len(skills)))
    spellsets['Wild'] = ('ensemble aléatoire de capacités', _wildskills)

    spellsets['Magic'] = ('sort de magie', list(range(0, 0x36)))
    spellsets['Black'] = ('sort de magie noire', list(range(0, 0x18)))
    spellsets['White'] = ('sort de magie blanche', list(range(0x2D, 0x36)))
    spellsets['Gray'] = ('sort de magie grise', list(range(0x18, 0x2D)))
    spellsets['Esper'] = ('invocation d\'Esper', list(range(0x36, 0x51)))
    spellsets['Sword'] = ('technique SwdTech', list(range(0x55, 0x5D)))
    spellsets['Blitz'] = ('Blitz', list(range(0x5D, 0x65)))
    spellsets['Geo'] = ('danse de type géomancien', list(range(0x65, 0x75)))
    spellsets['Beast'] = ('danse d\'invocation de bête', list(range(0x75, 0x7D)))
    spellsets['Lore'] = ('Lore', list(range(0x8B, 0xA3)))
    spellsets['Rare'] = ('effet rare (Slots, Super Ball, capacité de monstre hors-Lore)',
                         list(range(0x7D, 0x83)) + list(range(0xA3, 0xEE)))

    elementals = [s for s in skills if bin(s.elements).count('1') == 1]
    spellsets['Fire'] = ('capacité élémentaire feu', [s for s in elementals if s.elements & 1])
    spellsets['Ice'] = ('capacité élémentaire glace', [s for s in elementals if s.elements & 2])
    spellsets['Bolt'] = ('capacité élémentaire foudre', [s for s in elementals if s.elements & 4])
    spellsets['Bio'] = ('capacité élémentaire poison', [s for s in elementals if s.elements & 8])
    spellsets['Wind'] = ('capacité élémentaire vent', [s for s in elementals if s.elements & 0x10])
    spellsets['Pearl'] = ('capacité élémentaire sacrée', [s for s in elementals if s.elements & 0x20])
    spellsets['Earth'] = ('capacité élémentaire terre', [s for s in elementals if s.elements & 0x40])
    spellsets['Water'] = ('capacité élémentaire eau', [s for s in elementals if s.elements & 0x80])
    spellsets['Elem'] = ('capacité élémentaire (hors magie noire)',
                         [s for s in skills if s.elements and s.id not in range(0, 0x18)])

    spellsets['Nuke'] = ('dégâts magiques non-élémentaires',
                         [s for s in skills if s.power and not any(
                             [s.elements, s.percentage, s.physical, s.healing])])
    spellsets['Heal'] = ('soin PV/PM', [s for s in skills if s.healing])
    spellsets['Phys'] = ('capacité physique', [s for s in skills if s.physical])
    spellsets['Curse'] = ('altération d\'état nuisible (ennemi)',
                          [s for s in skills if all(
                              [s.target_enemy_default, not s.miss_if_death_prot, not s.power])])
    spellsets['Bless'] = ('altération d\'état bénéfique (allié)',
                          [s for s in skills if not any(
                              [s.target_enemy_default, s.power, s.id == 0xA4])])
    spellsets['Drain'] = ('vol de PV/PM', [s for s in skills if s.draining or s.concernsmp])

    death_ignore_protection = [name_id[n] for n in
                                ["Ragnarok", "Mind Blast", "Dread", "Soul Out"] if n in name_id]
    spellsets['Death'] = ('mort instantanée',
                          [s for s in skills if s.miss_if_death_prot and not s.percentage and s.has_status] +
                          [s for s in skills if s.id in death_ignore_protection])
    spellsets['Heavy'] = ('dégâts en pourcentage',
                          [s for s in skills if s.miss_if_death_prot and s.percentage])
    spellsets['All'] = ('cible alliés et ennemis',
                        [s for s in skills if s.target_everyone and not s.target_one_side_only])
    spellsets['Party'] = ('buff de groupe complet',
                          [s for s in skills if s.target_group_default and not s.target_enemy_default])

    spellsets['Time'] = ('capacité type Magie du Temps',
                         [0x10, 0x11, 0x12, 0x13, 0x19, 0x1B, 0x1F, 0x20, 0x22,
                          0x26, 0x27, 0x28, 0x2A, 0x2B, 0x34, 0x89, 0x9B, 0xA0,
                          0xC9, 0xDF])
    spellsets['Limit'] = ('Technique de Limite', limit_skills)
    spellsets['Level'] = ('capacité basée sur le niveau',
                          [s for s in skills if s.level_spell or
                           s.name in ["Flare Star", "Dischord", "Stone"]])
    spellsets['Miss'] = ('capacité à faible précision',
                         [s for s in skills if not s.unblockable and not s.level_spell and 0 < s.accuracy < 90])

    for key in list(spellsets.keys()):
        desc, spellset = spellsets[key]
        if not spellset:
            continue
        if isinstance(spellset[0], int):
            spellset = [s for s in skills if s.id in spellset]
        spellset = sorted(set(spellset), key=lambda s: s.id)
        spellsets[key] = (desc, spellset)

    return spellsets
