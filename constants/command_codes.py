"""
Adresses ROM par commande de combat, portées depuis commandcodes.txt de
Beyond Chaos (BeyondChaos/tables/commandcodes.txt).

Pour chaque commande vanilla :
- pointer  : entrée (2 octets) de la jump table qui détermine quel code
             s'exécute quand cette commande est choisie en combat. C'est
             CETTE entrée qu'on patche pour rediriger vers un skill_pools
             généré (write_spell_sub / write_random_spell_sub).
- start/end: bornes du code vanilla d'origine de la commande (à ne pas
             confondre avec pointer -- c'est la routine PAR DÉFAUT que
             l'entrée `pointer` référence avant toute modification).
- menu     : pointeur du menu graphique associé.
- textptr  : pointeur du nom affiché de la commande.
- target   : cible par défaut vanilla (enemy/self/allies/enemies/randally).

Vérifié : aucune de ces adresses n'est touchée par WC ailleurs dans le
projet (cf. /areas/ff6-randomizer.md pour le détail de l'investigation).
"""

CommandCode = None  # défini plus bas après la classe légère


class _CommandCode:
    __slots__ = ("pointer", "start", "end", "menu", "textptr", "target")

    def __init__(self, pointer, start, end, menu, textptr, target):
        self.pointer = pointer
        self.start = start
        self.end = end
        self.menu = menu
        self.textptr = textptr
        self.target = target


CommandCode = _CommandCode

# clefs alignées sur constants.commands.id_name (WC)
command_codes = {
    "Fight":   CommandCode(0x219C7, 0x215C8, 0x21676, 0x17CE9, 0x18cea0, "enemy"),
    "Item":    CommandCode(0x219C9, 0x21897, 0x21907, 0x17CEB, 0x18cea7, "self"),
    "Magic":   CommandCode(0x219CB, 0x21741, 0x2177D, 0x17CED, 0x18ceae, "self"),
    "Morph":   CommandCode(0x219CD, 0x21936, 0x2194C, 0x17CEF, 0x18ceb5, "self"),
    "Revert":  CommandCode(0x219CF, 0x21927, 0x21936, 0x17CF1, 0x18cebc, "self"),
    "Steal":   CommandCode(0x219D1, 0x21591, 0x2159D, 0x17CF3, 0x18cec3, "enemy"),
    "Capture": CommandCode(0x219D3, 0x21610, 0x21676, 0x17CF5, 0x18ceca, "enemy"),
    "SwdTech": CommandCode(0x219D5, 0x21847, 0x21885, 0x17CF7, 0x18ced1, "self"),
    "Throw":   CommandCode(0x219D7, 0x2188D, 0x21897, 0x17CF9, 0x18ced8, "self"),
    "Tools":   CommandCode(0x219D9, 0x21885, 0x2188D, 0x17CFB, 0x18cedf, "self"),
    "Blitz":   CommandCode(0x219DB, 0x2159D, 0x215C8, 0x17CFD, 0x18cee6, "self"),
    "Runic":   CommandCode(0x219DD, 0x2195B, 0x2196A, 0x17CFF, 0x18ceed, "self"),
    "Lore":    CommandCode(0x219DF, 0x2175F, 0x2177D, 0x17D01, 0x18cef4, "self"),
    "Sketch":  CommandCode(0x219E1, 0x2151F, 0x21560, 0x17D03, 0x18cefb, "enemy"),
    "Control": CommandCode(0x219E3, 0x21976, 0x2199D, 0x17D05, 0x18cf02, "enemy"),
    "Slot":    CommandCode(0x219E5, 0x21726, 0x2177D, 0x17D07, 0x18cf09, "self"),
    "Rage":    CommandCode(0x219E7, 0x21560, 0x21591, 0x17D09, 0x18cf10, "self"),
    "Leap":    CommandCode(0x219E9, 0x2199D, 0x219B2, 0x17D0B, 0x18cf17, "self"),
    "Mimic":   CommandCode(0x219EB, 0x2151E, 0x2151F, 0x17D0D, 0x18cf1e, "self"),
    "Dance":   CommandCode(0x219ED, 0x2177D, 0x217E5, 0x17D0F, 0x18cf25, "self"),
    "Row":     CommandCode(0x219EF, 0x21936, 0x2195B, 0x17D11, 0x18cf2c, "self"),
    "Def":     CommandCode(0x219F1, 0x2196A, 0x21976, 0x17D13, 0x18cf33, "self"),
    "Jump":    CommandCode(0x219F3, 0x217F6, 0x21847, 0x17D15, 0x18cf3a, "enemy"),
    "X Magic": CommandCode(0x219F5, 0x21741, 0x2177D, 0x17D17, 0x18cf41, "randally"),
    "GP Rain": CommandCode(0x219F7, 0x21907, 0x21927, 0x17D19, 0x18cf48, "enemies"),
    "Summon":  CommandCode(0x219F9, 0x21763, 0x2177D, 0x17D1B, 0x18cf4f, "self"),
    "Health":  CommandCode(0x219FB, 0x2171E, 0x21726, 0x17D1D, 0x18cf56, "allies"),
    "Shock":   CommandCode(0x219FD, 0x2171A, 0x21726, 0x17D1F, 0x18cf5d, "enemies"),
    "Possess": CommandCode(0x219FF, 0x217E5, 0x217F6, 0x17D21, 0x18cf64, "enemy"),
    "MagiTek": CommandCode(0x21A01, 0x2175F, 0x2177D, 0x17D23, 0x18cf6b, "self"),
}
