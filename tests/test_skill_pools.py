import random
import sys
import unittest


class FakeRom:
    """Substitut minimal de memory.rom.ROM : juste assez pour que les
    écritures ASM déclenchées à l'IMPORT de data.skill_pools (via
    instruction.c2, qui alloue/écrit une routine dès son chargement)
    trouvent un Space.rom fonctionnel, sans dépendre d'un vrai fichier
    ROM (absent du dépôt, comme pour le reste de la suite de tests)."""

    def __init__(self, size = 4 * 2 ** 20):
        self.data = [0xff] * size

    def get_byte(self, address):
        return self.data[address]

    def get_bytes(self, address, count):
        return self.data[address : address + count]

    def set_bytes(self, address, values):
        values = list(values)
        self.data[address : address + len(values)] = values
        return address + len(values)


def _import_skill_pools():
    # comme pour les autres modules "args"-dépendants du projet, importer
    # data.skill_pools nécessite un sys.argv valide (voir tests/test_innate_relics.py) ;
    # de plus, instruction.c2 (importé par data.skill_pools) alloue et
    # écrit une routine ASM dès l'import du module -- il faut donc un
    # Space.rom et des heaps initialisés avant l'import, une seule fois.
    original_argv = sys.argv
    sys.argv = ["test", "-i", "dummy.smc"]
    try:
        import memory.space as space_module
        if space_module.Space.rom is None:
            space_module.Space.rom = FakeRom()
            import memory.free
            memory.free.free()

        from data.skill_pools import choose_exclusive_carrier_command, resolve_carrier_slot, CARRIER_POOL
    finally:
        sys.argv = original_argv
    return choose_exclusive_carrier_command, resolve_carrier_slot, CARRIER_POOL


choose_exclusive_carrier_command, resolve_carrier_slot, CARRIER_POOL = _import_skill_pools()

VANILLA_COMMANDS = ["Fight", "Magic", "Item", "Row", "Def", "Mimic", "Summon", "Possess", "Leap"]


class TestChooseExclusiveCarrierCommand(unittest.TestCase):
    def test_never_reassigns_a_command_already_used_globally(self):
        pool = list(CARRIER_POOL)
        used_globally = {pool[0], pool[1]}
        for _ in range(50):
            chosen = choose_exclusive_carrier_command(pool, used = set(), used_globally = used_globally)
            self.assertNotIn(chosen, used_globally)

    def test_never_reassigns_a_command_already_used_by_this_character(self):
        pool = list(CARRIER_POOL)
        used = {pool[0]}
        for _ in range(50):
            chosen = choose_exclusive_carrier_command(pool, used = used, used_globally = set())
            self.assertNotIn(chosen, used)

    def test_returns_none_when_pool_is_exhausted_never_a_reused_duplicate(self):
        # exclusivité STRICTE, sans exception : une fois tout le pool
        # distribué, la fonction ne doit JAMAIS rendre une commande déjà
        # utilisée ailleurs -- elle doit renvoyer None et laisser
        # l'appelant décider (ne rien assigner de nouveau), jamais choisir
        # elle-même un doublon "en dernier recours"
        pool = list(CARRIER_POOL)
        used_globally = set(pool)  # tout le pool déjà distribué
        for _ in range(50):
            chosen = choose_exclusive_carrier_command(pool, used = set(), used_globally = used_globally)
            self.assertIsNone(chosen)

    def test_many_requests_never_produce_a_duplicate_assignment(self):
        # tant que le nombre de demandes ne dépasse pas la taille du pool,
        # exactement len(pool) assignations uniques ; au-delà, None --
        # jamais un doublon, à aucun moment
        pool = list(CARRIER_POOL)
        used_globally = set()
        assigned = []
        random.seed(42)
        for _ in range(len(pool) + 10):  # plus de demandes que de commandes disponibles
            chosen = choose_exclusive_carrier_command(pool, used = set(), used_globally = used_globally)
            if chosen is not None:
                used_globally.add(chosen)
                assigned.append(chosen)

        self.assertEqual(len(assigned), len(pool))
        self.assertEqual(len(assigned), len(set(assigned)))  # aucun doublon
        self.assertEqual(set(assigned), set(pool))  # tout le pool est sorti, chacun une fois

    def test_vanilla_commands_are_not_part_of_the_exclusive_pool(self):
        for vanilla_command in VANILLA_COMMANDS:
            self.assertNotIn(vanilla_command, CARRIER_POOL)


class TestModLoopPreservesExistingCommandWhenPoolExhausted(unittest.TestCase):
    # simule la boucle par-personnage de SkillPools.mod() (sans ROM/ASM
    # réels) : quand le pool -rsk est épuisé, le slot doit garder EXACTEMENT
    # ce qu'il contenait déjà avant que le système n'y touche (simulant un
    # nom vanilla/natif préexistant hors de CARRIER_POOL et hors de
    # Fight/Magic, ex. "Row"), jamais une commande -rsk réutilisée, jamais
    # une commande vanilla précise imposée à sa place.
    def test_overflow_characters_keep_their_preexisting_command_not_a_duplicate_skill(self):
        pool = list(CARRIER_POOL)
        used_globally = set()
        character_count = len(pool) + 5  # volontairement plus de personnages que de skills
        preexisting_command = "Row"  # vanilla, hors de CARRIER_POOL, hors de Fight/Magic -- repli sûr
        assignments = []

        for _ in range(character_count):
            used = set()
            chosen = resolve_carrier_slot(pool, used, used_globally, preexisting_command)
            used.add(chosen)
            if chosen in pool:
                used_globally.add(chosen)
            assignments.append(chosen)

        carrier_assignments = [a for a in assignments if a in pool]
        preexisting_assignments = [a for a in assignments if a == preexisting_command]

        self.assertEqual(len(carrier_assignments), len(set(carrier_assignments)))  # exclusivité stricte respectée
        self.assertEqual(len(carrier_assignments), len(pool))  # tout le pool utilisé, une fois chacun
        self.assertEqual(len(preexisting_assignments), character_count - len(pool))  # le reste garde l'existant
        for vanilla_command in VANILLA_COMMANDS:
            if vanilla_command != preexisting_command:
                self.assertNotIn(vanilla_command, assignments)  # aucune AUTRE commande vanilla injectée

    def test_preexisting_carrier_command_reused_only_if_not_already_claimed(self):
        # cas résiduel : le contenu préexistant du slot est LUI-MÊME une
        # commande de CARRIER_POOL (ex. un -com explicite l'y avait placée
        # avant que notre système ne tourne). S'il n'a encore été réclamé
        # par personne, il est un repli sûr. S'il est déjà réclamé par un
        # autre personnage, resolve_carrier_slot ne doit JAMAIS le
        # renvoyer (ce serait un doublon) -- elle doit se replier sur "Item".
        pool = list(CARRIER_POOL)
        preexisting = pool[0]

        # pool épuisé, mais le contenu préexistant n'a encore été réclamé
        # par personne -- repli sûr, autorisé
        used_globally_unclaimed = set(pool[1:])  # tout sauf preexisting
        chosen = resolve_carrier_slot(pool, used = set(), used_globally = used_globally_unclaimed,
                                       current_name = preexisting)
        self.assertEqual(chosen, preexisting)

        # pool épuisé ET le contenu préexistant déjà réclamé par un autre
        # personnage -- aucun repli sûr, doit se replier sur "Item" (jamais un doublon)
        used_globally_claimed = set(pool)  # tout, y compris preexisting
        chosen = resolve_carrier_slot(pool, used = set(), used_globally = used_globally_claimed,
                                       current_name = preexisting)
        self.assertEqual(chosen, "Item")

    def test_fight_or_magic_as_preexisting_content_never_leaks_into_slot_3_or_4(self):
        # LE cas signalé : le contenu préexistant d'un slot (avant que
        # notre système n'y touche) est fréquemment "Magic" en vanilla
        # (3e commande par défaut chez beaucoup de personnages). Une fois
        # le pool -rsk épuisé, ce contenu ne doit JAMAIS être préservé tel
        # quel -- Fight/Magic sont réservées au slot 1 par -rsk lui-même.
        pool = list(CARRIER_POOL)
        used_globally = set(pool)  # pool totalement épuisé
        for reserved_command in ("Fight", "Magic"):
            chosen = resolve_carrier_slot(pool, used = set(), used_globally = used_globally,
                                           current_name = reserved_command)
            self.assertNotEqual(chosen, reserved_command)
            self.assertEqual(chosen, "Item")

    def test_item_as_preexisting_content_never_leaks_into_slot_3(self):
        # même principe que Fight/Magic, appliqué à Item : le slot 3
        # (extra_forbidden=("Item",)) ne doit jamais conserver "Item" comme
        # contenu préexistant, même quand le pool -rsk est épuisé -- Item
        # est réservé au slot 4 (50% de chances), jamais au slot 3, et ne
        # doit jamais pouvoir apparaître simultanément aux deux. Utilise le
        # vrai repli du slot 3 en production : "None" (emplacement vide),
        # jamais une commande vanilla nommée.
        pool = list(CARRIER_POOL)
        used_globally = set(pool)  # pool totalement épuisé
        chosen = resolve_carrier_slot(pool, used = set(), used_globally = used_globally,
                                       current_name = "Item", extra_forbidden = ("Item",), fallback = "None")
        self.assertNotEqual(chosen, "Item")
        self.assertEqual(chosen, "None")

    def test_item_as_preexisting_content_still_safe_for_slot_4(self):
        # à l'inverse, le slot 4 (paramètres par défaut, sans
        # extra_forbidden) doit continuer à accepter "Item" comme contenu
        # préexistant -- c'est son emplacement légitime, comportement
        # inchangé par ce correctif.
        pool = list(CARRIER_POOL)
        used_globally = set(pool)  # pool totalement épuisé
        chosen = resolve_carrier_slot(pool, used = set(), used_globally = used_globally,
                                       current_name = "Item")
        self.assertEqual(chosen, "Item")


    def test_row_and_def_are_protected_before_reaching_resolve_carrier_slot(self):
        # Row/Def ne sont PAS filtrées par resolve_carrier_slot elle-même
        # (elle ne connaît que Fight/Magic/Item) -- leur protection vient
        # de PROTECTED_ALWAYS, vérifié plus haut dans la boucle de
        # SkillPools.mod() AVANT tout appel à resolve_carrier_slot (voir
        # data/skill_pools.py, la boucle "for slot in range(...)") : si
        # current_name est dans PROTECTED_ALWAYS, la boucle continue sans
        # jamais appeler resolve_carrier_slot. Garde-fou de régression :
        # Row/Def doivent rester dans cette liste.
        from data.skill_pools import PROTECTED_ALWAYS
        self.assertIn("Row", PROTECTED_ALWAYS)
        self.assertIn("Def", PROTECTED_ALWAYS)


if __name__ == "__main__":
    unittest.main()
