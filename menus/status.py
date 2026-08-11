from memory.space import Bank, Reserve, Allocate, Write, Read
import instruction.asm as asm
import args

class StatusMenu:
    def __init__(self, characters, innate_relics, items):
        self.free_space = Allocate(Bank.C3, 61, "status menu")
        self.characters = characters
        self.innate_relics = innate_relics
        self.items = items

        self.mod()

    def mod_natural_magic(self):
        import data.text as text

        natural_magic_learners = []
        if self.characters.natural_magic.learner1 is not None:
            natural_magic_learners.append(self.characters.natural_magic.learner1)
        if self.characters.natural_magic.learner2 is not None:
            natural_magic_learners.append(self.characters.natural_magic.learner2)

        if not natural_magic_learners:
            return

        empty_position_text = self.free_space.next_address
        self.free_space.write(
            0xb7, 0x3a, # x/y position
            text.get_bytes("       ", text.TEXT3),
            0x00,       # end
        )

        natural_position_text = self.free_space.next_address
        self.free_space.write(
            0xb7, 0x3a, # x/y position
            text.get_bytes("Natural", text.TEXT3),
            0x00,       # end
        )

        draw_lv_hp_mp_natural = self.free_space.next_address
        self.free_space.copy_from(0x35d58, 0x35d5a) # call draw LV/HP/MP

        # status menu and lineup store character data/slots in ram differently
        # status menu can also be reached from main menu or L/R switching
        self.free_space.write(
            asm.LDA(0x25, asm.DIR),     # a = main menu cursor pos (set to zero for lineup at c36328)
            asm.CMP(0x04, asm.IMM8),    # status menu reached from main menu?
            asm.BNE("LINEUP_MENU"),     # branch if not

            asm.XY8(),
            asm.LDX(0x28, asm.DIR),     # x = character slot
            asm.LDA(0x69, asm.DIR_X),   # a = character id
            asm.XY16(),
            asm.BRA("LEARNER_CHECK"),

            "LINEUP_MENU",
            asm.LDA(0xc9, asm.DIR),     # load character id

            "LEARNER_CHECK",
        )
        for learner in natural_magic_learners:
            self.free_space.write(
                asm.CMP(learner, asm.IMM8), # compare character with learner
                asm.BEQ("DRAW_NATURAL"),
            )

        # if not a natural magic learner, write spaces to cover up "Natural" in case switching characters using L/R
        # this is also how MP display is handled (c30cba)
        self.free_space.write(
            "DRAW_EMPTY",
            asm.LDY(empty_position_text, asm.IMM16),
            asm.BRA("DRAW_TEXT_RETURN"),

            "DRAW_NATURAL",
            asm.LDY(natural_position_text, asm.IMM16),

            "DRAW_TEXT_RETURN",
            asm.JSR(0x02f9, asm.ABS),   # call draw text
            asm.RTS(),
        )

        space = Reserve(0x35d58, 0x35d5a, "status draw LV/HP/MP and Natural", asm.NOP())
        space.write(
            asm.JSR(draw_lv_hp_mp_natural, asm.ABS),
        )

    def mod_stat_colors(self):
        # code couleur des valeurs numériques de l'écran de statut, selon
        # l'écart par rapport à la valeur vanilla de référence de chaque
        # personnage (même donnée que -csrp, capturée de façon additive
        # dans data/characters.py::stats_random_percent()).
        #
        # Point d'accroche identifié et vérifié DIRECTEMENT dans la ROM
        # fournie (FFIII_1_0.smc, hash validé par WC lui-même) : bloc
        # unique et rectiligne de 126 octets (C3/5FCB-C3/6048, adresses
        # WC 0x35FCB-0x36048), qui dessine les 9 valeurs de l'écran de
        # statut à la suite. Aucun branchement interne (vérifié par
        # analyse séquentielle stricte de chaque segment) -- sûr à
        # reloger, contrairement au hook des reliques innées.
        #
        # Ne modifie ni le calcul, ni le stockage, ni la valeur des
        # statistiques -- uniquement la couleur ($29) appliquée juste
        # avant chaque dessin de nombre.
        if not getattr(args, "character_stat_random_percent", False):
            return

        stat_random_percents = getattr(self.characters, "stat_random_percents", None)
        if not stat_random_percents:
            return

        from data.characters import Characters

        # PLAN B -- SYSTÈME À 3 COULEURS, 100% VANILLA (09/08, après
        # nouvelles captures montrant que même des lignes de palette
        # écrites une seule fois -- pourtant le pattern déjà prouvé sur le
        # nom -- produisent encore un rendu "blanc épais/brillant"
        # incohérent sur certains chiffres, tandis que le cyan (ligne 1,
        # 100% vanilla, aucune écriture de notre part) s'affiche
        # parfaitement à chaque tentative depuis le tout premier test.
        #
        # DIAGNOSTIC (ce qui differe entre un nom coloré qui fonctionne et
        # un chiffre de stat qui ne fonctionne pas) : dans TOUS les essais
        # qui ont échoué à produire une couleur nette sur les chiffres
        # (lignes 5/6/7 dynamiques, puis lignes 4/5/6 statiques), le point
        # commun est que la ligne de palette concernée est une ligne que
        # NOUS avons dû écrire nous-mêmes (données personnalisées). Le
        # seul rendu qui a fonctionné à 100% de manière reproductible dans
        # tous les tests, y compris le tout premier (le nom en rouge) et
        # celui-ci (Mag.Pwr et MBlock en cyan net, capture utilisateur),
        # est justement celui qui ne nécessite AUCUNE écriture de notre
        # part : le cyan (ligne 1, \$29=0x24), déjà entièrement initialisé
        # par le vanilla lui-même. Cela pointe vers une dernière source
        # possible de différence non encore isolée entre nos lignes
        # personnalisées et les lignes 100% vanilla (peut-être liée à la
        # façon dont le chargement initial de la police vanilla, séparé
        # de notre propre écriture, interagit avec la CGRAM/VRAM à un
        # niveau que nous n'avons pas encore identifié avec certitude) --
        # plutôt que de continuer à chercher dans un temps qui devient
        # déraisonnable, décision prise avec l'utilisateur de basculer sur
        # un système plus modeste mais entièrement fiable.
        #
        # Plutôt que de réutiliser une couleur personnalisée non fiable
        # pour la catégorie basse, on utilise la ligne 2 (\$29=0x28) --
        # déjà caractérisée précédemment comme un gris uniforme
        # (contour ET remplissage gris, ~65/123 sur 255), utilisée par le
        # vanilla pour du texte "grisé/désactivé" -- qui a l'avantage
        # d'être, comme le cyan, 100% vanilla et déjà initialisée : AUCUNE
        # écriture de palette personnalisée n'est plus nécessaire nulle
        # part dans cette méthode, ce qui élimine intégralement la classe
        # de bug rencontrée depuis plusieurs tours.
        #
        # Seuils : gris pour BASSE, blanc pour NORMALE, cyan pour HAUTE.
        # Ces 3 couleurs restent EXACTEMENT celles validées au tour
        # précédent (100% vanilla, aucune écriture de palette) -- seule
        # la RÈGLE qui détermine la catégorie change dans cette révision.
        COLOR_GRAY = 0x28         # confirmé dans la ROM (texte "grisé")
        COLOR_WHITE = 0x20        # confirmé dans la ROM
        COLOR_LIGHT_BLUE = 0x24   # confirmé dans la ROM (cyan)

        # RÈGLE DE CLASSIFICATION (09/08, 2e révision) -- abandonne la
        # comparaison entre personnages (quartiles des 14 valeurs
        # vanilla) au profit du pourcentage RÉELLEMENT TIRÉ par World
        # Collide pour ce personnage et cette statistique
        # (data/characters.py::stats_random_percent(), capturé de façon
        # additive dans self.characters.stat_random_percents -- aucun
        # nouveau nombre aléatoire généré, uniquement le tirage existant
        # observé avant troncature/écrêtage). Objectif demandé : indiquer
        # si CE tirage s'écarte sensiblement de 100% (= valeur vanilla de
        # CE personnage), pas comparer les personnages entre eux. Résout
        # aussi le problème de troncature de l'ancienne comparaison
        # final/vanilla recalculée après coup (ex. Edgar MBlock vanilla=1
        # -> seul 0% ou -100% possibles) puisqu'on lit directement le
        # pourcentage réel tiré, jamais un rapport d'entiers.
        #
        # Seuils validés : <90% BASSE, 90-110% NORMALE, >110% HAUTE.
        # Exprimés en pourcentage absolu (par rapport à 100%, la valeur
        # vanilla), donc indépendants de la plage -csrp choisie par
        # l'utilisateur -- une plage étroite (ex. 95-105%) donnera
        # naturellement presque tout en NORMALE, une plage large (ex.
        # 50-150%) fera ressortir BASSE/HAUTE plus souvent, dans les deux
        # cas le seuil continue à mesurer un écart réel par rapport à la
        # valeur vanilla du personnage.
        #
        # Stat vanilla = 0 : aucun tirage n'est effectué par
        # stats_random_percent() dans ce cas (comportement WC inchangé),
        # donc pas d'entrée dans stat_random_percents -- .get() renvoie
        # None et color_for() retombe sur NORMALE, comme précédemment.
        PERCENT_LOW_THRESHOLD = 0.90
        PERCENT_HIGH_THRESHOLD = 1.10

        def color_for(stat_name, character):
            percent = stat_random_percents.get(character.id, {}).get(stat_name)
            if percent is None:
                return COLOR_WHITE
            if percent < PERCENT_LOW_THRESHOLD:
                return COLOR_GRAY
            if percent > PERCENT_HIGH_THRESHOLD:
                return COLOR_LIGHT_BLUE
            return COLOR_WHITE

        # (nom de stat WC, adresse RAM de début de segment, adresse RAM de
        # fin de segment inclusive) -- vérifiés octet par octet directement
        # dans la ROM fournie, dans cet ordre exact
        STAT_SEGMENTS = [
            ("init_vigor",         0x35FCF, 0x35FDA),
            ("init_speed",         0x35FDB, 0x35FE6),
            ("init_stamina",       0x35FE7, 0x35FF2),
            ("init_magic",         0x35FF3, 0x35FFE),
            ("init_attack",        0x35FFF, 0x36018),  # Bat.Pwr -- routine différente (16 bits) mais même position de couleur
            ("init_defense",       0x36019, 0x36024),
            ("init_evasion",       0x36025, 0x36030),
            ("init_magic_defense", 0x36031, 0x3603C),
            ("init_magic_evasion", 0x3603D, 0x36048),
        ]

        HOOK_START = 0x35FCB
        HOOK_END = 0x36048  # inclusif -- 126 octets au total

        # plus aucune initialisation de palette : les 3 couleurs utilisées
        # (gris/blanc/cyan) sont TOUTES déjà initialisées par le vanilla
        # lui-même, aucune écriture dans \$7E3049 n'est plus nécessaire.
        src = []
        for stat_index, (stat_name, seg_start, seg_end) in enumerate(STAT_SEGMENTS):
            # table personnage -> couleur pour CETTE stat (taille fixe,
            # un octet par personnage jouable, calculée entièrement en
            # Python -- aucune arithmétique de pourcentage en assembleur)
            color_table = [COLOR_WHITE] * Characters.CHARACTER_COUNT
            for character in self.characters.characters:
                if character.id < Characters.CHARACTER_COUNT:
                    color_table[character.id] = color_for(stat_name, character)
            color_snes = Write(Bank.C3, color_table, f"status stat colors: {stat_name}").start_address_snes

            # détermine l'id du personnage actuellement affiché -- vérifié
            # directement dans les octets de la ROM que ce bloc précis
            # (C3/5F8E, juste avant notre point d'accroche) utilise
            # TOUJOURS $28 (numéro de slot 0-3) puis $69,X pour obtenir
            # l'id du personnage, sans jamais passer par $25/$c9 (mécanisme
            # différent, propre à mod_natural_magic() ci-dessus, pour un
            # point d'accroche différent de l'écran de statut).
            #
            # BUG CORRIGÉ (09/08, diagnostic registres) -- deux causes
            # cumulées de la corruption persistante, aucune liée au choix
            # des couleurs elles-mêmes :
            #
            # 1) TAX était exécuté APRÈS repassage en X 16 bits (XY16()),
            # juste après un LDA 8 bits ($69,X). Sur 65816, TAX transfère
            # le registre C (accumulateur complet 16 bits, B:A) quand X
            # est en 16 bits, quel que soit la largeur de A -- l'octet
            # haut B n'est PAS remis à zéro par un LDA 8 bits ni par SEP
            # #$20, il peut contenir un résidu d'une opération 16 bits
            # antérieure ailleurs dans la routine englobante. Résultat :
            # X pouvait valoir (B_résiduel<<8)|id_personnage, un index
            # totalement hors de la table de couleurs (14 octets) -> lit
            # un octet arbitraire de la ROM comme "couleur" -> corruption,
            # même quand les couleurs choisies dans la table elle-même
            # étaient valides (elles n'étaient simplement jamais lues au
            # bon endroit). Correction : le TAX est fait AVANT XY16(),
            # pendant que X est encore 8 bits -- l'octet haut de X a été
            # forcé à zéro par le SEP #$10 de XY8() et reste à zéro tant
            # qu'aucune opération 16 bits ne le modifie, donc TAX en 8
            # bits ne transfère proprement que l'id personnage (0-13).
            #
            # 2) La lecture de la table utilisait l'adressage absolu court
            # (ABS_X, .start_address) plutôt que long (LNG_X,
            # .start_address_snes). L'adressage absolu dépend du registre
            # DBR courant, or le code vanilla environnant (confirmé par
            # désassemblage : lectures "LDA \$11A6" etc. sur des adresses
            # \$11xx, qui ne peuvent être que de la RAM \$7Exxxx puisque
            # les banques C0-FF sont de la ROM pure sans miroir RAM) prouve
            # que DBR vaut \$7E à cet endroit précis de la routine, pas
            # \$C3. Un ABS_X sur notre table (physiquement en banque C3)
            # lisait donc en réalité de la RAM \$7E:table -- des octets
            # sans rapport -- au lieu de notre table de couleurs. Ce même
            # motif (table en banque C3, lue depuis un hook où DBR peut
            # valoir autre chose) est déjà résolu ailleurs dans WC via
            # LNG_X + start_address_snes (voir menus/rage.py, menus/buy.py) ;
            # appliqué ici à l'identique.
            src += [
                asm.XY8(),
                asm.LDX(0x28, asm.DIR),
                asm.LDA(0x69, asm.DIR_X),
                asm.TAX(),
                asm.XY16(),
                asm.LDA(color_snes, asm.LNG_X),
                asm.STA(0x29, asm.DIR),
            ]

            # rejoue fidèlement le segment original -- lu directement
            # depuis la ROM fournie (pas de transcription manuelle),
            # strictement inchangé (calcul/affichage de la valeur intacts)
            original_segment = Read(seg_start, seg_end)
            src.append(original_segment)

        # BUG DIAGNOSTIQUÉ ET CORRIGÉ (09/08, captures utilisateur : nom
        # du personnage coloré au lieu des chiffres de stats) -- vérifié
        # directement dans la ROM vanilla, PAS seulement dans les
        # commentaires : le vanilla d'origine ne réglait \$29 QU'UNE SEULE
        # FOIS avant Vigor (LDA #$20; STA \$29 à l'ancien C3/5FCB) et ne le
        # touchait plus jamais jusqu'à C3/605E (juste après la fin de
        # notre bloc de 126 octets), où le vanilla le remet explicitement
        # à 0x20 avant de continuer à dessiner "Your Exp:"/"For level up:"
        # (JSR \$34CF/\$34E5/\$34E6 en C3/604C-605B, DANS LA MÊME
        # séquence d'affichage, exécutés juste après notre bloc et AVANT
        # ce reset vanilla) puis, plus loin encore, LV/HP/MP et les icônes
        # de statut. Le vanilla comptait donc implicitement sur le fait
        # que \$29 ne changeait jamais entre Vigor et ce reset -- une
        # hypothèse que notre hook casse forcément puisqu'on fait
        # varier \$29 neuf fois (une fois par stat, c'est tout l'intérêt).
        # Résultat : à la fin de notre routine, \$29 contenait la couleur
        # de la 9ᵉ stat (MBlock/évasion magique), et cette couleur
        # "fuyait" sur tout ce que le vanilla dessine ensuite avant son
        # propre reset (604C-605B), avant même d'atteindre le nom -- la
        # cause est la même fuite, peu importe l'élément visuel exact
        # affecté en premier.
        #
        # Correction minimale et ciblée, qui ne touche ni au point
        # d'accroche, ni au mécanisme de sélection de couleur par stat
        # (TAX/XY16/LNG_X, inchangé), ni aux segments vanilla rejoués :
        # remettre \$29 à 0x20 nous-mêmes, à l'intérieur de NOTRE routine,
        # juste après le dessin de la 9ᵉ et dernière stat et avant notre
        # propre RTS -- exactement le même réflexe que fait déjà le
        # vanilla lui-même à plusieurs endroits de cette routine (605E,
        # 62DD) après chaque élément coloré ponctuellement. Ainsi la
        # couleur calculée reste strictement confinée aux 9 valeurs
        # numériques des stats, et tout ce qui est dessiné après (Exp,
        # LV/HP/MP, icônes, nom, etc.) retrouve le blanc normal dès la
        # sortie de notre routine, comme le vanilla l'attend.
        src.append(asm.LDA(0x20, asm.IMM8))
        src.append(asm.STA(0x29, asm.DIR))

        src.append(asm.RTS())  # retourne juste après le JSR du point d'accroche

        space = Write(Bank.C3, src, "status stat colors: draw hook")

        # seuls 3 octets réels sont écrits au point d'accroche (JSR) ; le
        # reste de la plage réservée est comblé de NOP puis retombe
        # naturellement dans le code vanilla qui continue après ce bloc
        # (affichage de l'XP, notamment) -- pas de RTS ici, ce serait un
        # retour prématuré de la fonction englobante
        hook = Reserve(HOOK_START, HOOK_END, "status stat colors: redirect", asm.NOP())
        hook.write(
            asm.JSR(space.start_address, asm.ABS),
        )

    def mod_innate_relic_display(self):
        # POSITION_X/POSITION_Y ARE NOT SCREEN COORDINATES. $C3/02F9 (the draw routine, disassembled
        # directly) packs these two bytes into a single 16-bit value (low=X, high=Y) and uses it as a
        # $7E:YYXX WRAM pointer into the status screen's tile+color buffer.
        #
        # Both values are now cross-checked against Beyond Chaos's own working implementation of this
        # exact feature (BeyondChaosRandomizer/BeyondChaos/patches.py::hidden_relic(), "Status Screen
        # Display"), not just our own guesses:
        # - BC positions its relic name with "LDY #$391D ; JSR $3519". Disassembling $3519 (present,
        #   unmodified, in this rom too) shows it packs Y with the exact same low=X/high=Y convention
        #   $02F9 uses, just staged through the hardware WRAM port ($2180-2183) into a scratch buffer
        #   at $9E89 first and blitted via $02FF, instead of read straight from a rom blob via $02F9.
        #   Different pipeline, same destination-address math -- so BC's own proven value decodes to
        #   X=0x1D, Y=0x39 in our own terms.
        # - Y=0x39 independently matches where our own bisection already landed (0x37 confirmed
        #   invisible in-game, 0x3a -- mod_natural_magic()'s own row -- confirmed visible by
        #   screenshot; 0x39 is the smallest step up from the known-good row, and also the lowest row
        #   used anywhere else in this rom by a completely different screen sharing this same buffer,
        #   the Config menu).
        # - X=0x1D is far to the left of the 0x90/0xb7 values tried before, which is almost certainly
        #   why those overflowed into unrelated memory (visible in-game as stray letters wrapping to
        #   the screen's top corners and a bogus line injected into the command list box): the row's
        #   real usable width starts much further left than assumed. Our field (12 characters, the
        #   pool's real longest name) now ends at byte 0x1D+12*2=0x35 -- inside the same low-byte
        #   range other confirmed-safe text on this row family already uses (e.g. the Config menu grid
        #   at 0x25/0x35), not just barely fitting.
        POSITION_X = 0x1d
        POSITION_Y = 0x39

        # matches "Natural"'s own color exactly, per direct request. mod_natural_magic() doesn't set
        # $29 itself -- it inherits whatever color Block2 (its own hook's immediate predecessor,
        # 0x35d4e: "LDA #$24 ; STA $29") already set right before mod_natural_magic()'s own JSR $69BA
        # at 0x35d58. That's 0x24, and it's confirmed to render as cyan in-game (screenshot). Using
        # that same literal value here, rather than 0x2c, which turned out not to match.
        TEXT_COLOR = 0x24

        # distinct 3-byte call site from the one mod_natural_magic() already uses (0x35d58-0x35d5a).
        # both redirect the exact same shared vanilla subroutine (JSR $69BA, one of four near-identical
        # calls in the LV/HP/MP draw block at 0x35d20-0x35d7c) at different, otherwise-untouched call
        # sites, so the two features can coexist without any Reserve() conflict.
        HOOK_START = 0x35d4b
        HOOK_END = 0x35d4d

        if not self.innate_relics.relic_assignments:
            return

        import data.text as text

        NAME_WIDTH = 12  # true longest name in InnateRelics' own pool (verified below), not the
                          # vanilla item-name field's fixed 13 -- e.g. "Gold Hairpin"/"MithrilGlove"

        # defensive check: if InnateRelics' pool ever grows a longer name, fail loudly here instead of
        # silently truncating (which would misrepresent which relic a character actually has) or
        # silently overflowing this row's usable width again (see the width-overflow fix above)
        longest_actual = max((len(self.items.get_name(item_id))
                               for item_id in self.innate_relics.relic_pool()[0] + self.innate_relics.relic_pool()[1]),
                              default = 0)
        assert longest_actual <= NAME_WIDTH, \
            f"innate relic pool now has a name longer than NAME_WIDTH ({longest_actual} > {NAME_WIDTH}) -- " \
            f"raise NAME_WIDTH and re-check the row's usable width before widening POSITION_X's margin"

        display_space = Allocate(Bank.C3, self._innate_relic_display_size(), "status innate relic display")

        empty_position_text = display_space.next_address
        display_space.write(
            POSITION_X, POSITION_Y,
            text.get_bytes(" " * NAME_WIDTH, text.TEXT3),
            0x00,
        )

        relic_position_texts = {}
        for character_id, item_id in self.innate_relics.relic_assignments.items():
            name = self.items.get_name(item_id).ljust(NAME_WIDTH)
            relic_position_texts[character_id] = display_space.next_address
            display_space.write(
                POSITION_X, POSITION_Y,
                text.get_bytes(name, text.TEXT3),
                0x00,
            )

        draw_relic_name = display_space.next_address
        display_space.copy_from(HOOK_START, HOOK_END)  # replay the original JSR $69BA we're overwriting

        # same dual-context character detection already used and validated in mod_natural_magic() above:
        # status menu reached from main menu vs lineup menu store the currently displayed character
        # differently, and status menu can also be reached via L/R switching between characters
        display_space.write(
            asm.LDA(0x25, asm.DIR),     # a = main menu cursor pos (set to zero for lineup at c36328)
            asm.CMP(0x04, asm.IMM8),    # status menu reached from main menu?
            asm.BNE("LINEUP_MENU"),     # branch if not

            asm.XY8(),
            asm.LDX(0x28, asm.DIR),     # x = character slot
            asm.LDA(0x69, asm.DIR_X),   # a = character id
            asm.XY16(),
            asm.BRA("CHARACTER_CHECK"),

            "LINEUP_MENU",
            asm.LDA(0xc9, asm.DIR),     # load character id

            "CHARACTER_CHECK",
        )
        for character_id in relic_position_texts:
            display_space.write(
                asm.CMP(character_id, asm.IMM8),
                asm.BEQ(f"DRAW_{character_id}"),
            )

        # no character matched -> this character has no innate relic: write spaces to cover up any
        # relic name left over from a previous character when switching via L/R (same trick
        # mod_natural_magic() uses for "Natural" above)
        display_space.write(
            "DRAW_EMPTY",
            asm.LDY(empty_position_text, asm.IMM16),
            asm.BRA("DRAW_TEXT_RETURN"),
        )
        for character_id, text_address in relic_position_texts.items():
            display_space.write(
                f"DRAW_{character_id}",
                asm.LDY(text_address, asm.IMM16),
                asm.BRA("DRAW_TEXT_RETURN"),
            )

        display_space.write(
            "DRAW_TEXT_RETURN",
            asm.LDA(TEXT_COLOR, asm.IMM8),
            asm.STA(0x29, asm.DIR),     # $02F9 reads this direct-page byte as the text color
            asm.JSR(0x02f9, asm.ABS),   # call draw text
            asm.RTS(),
        )

        hook = Reserve(HOOK_START, HOOK_END, "status innate relic display (redirect)", asm.NOP())
        hook.write(
            asm.JSR(draw_relic_name, asm.ABS),
        )

    def _innate_relic_display_size(self):
        # one text blob (2 bytes position + 13 bytes name + 1 byte terminator = 16) per character with
        # an innate relic, plus one shared blank blob (16); the 3 replayed hook bytes plus the
        # character-detection preamble (3 + 18 = 21 bytes, fixed); one CMP/BEQ pair (4 bytes) and one
        # LDY/BRA pair (5 bytes) per character with a relic, plus the shared DRAW_EMPTY block (5 bytes)
        # and the final color-set + JSR/RTS (4 + 4 = 8 bytes)
        character_count = len(self.innate_relics.relic_assignments)
        return (16 * (character_count + 1)) + 21 + (4 * character_count) + 5 + (5 * character_count) + 8

    def mod(self):
        if args.natural_magic_menu_indicator:
            self.mod_natural_magic()

        if args.random_innate_relics:
            self.mod_innate_relic_display()

        # CORRIGÉ (09/08, diagnostic registres complet, validé en jeu par
        # l'utilisateur : plus aucune corruption) : deux bugs cumulés
        # causaient la corruption, indépendants du choix des couleurs --
        # (1) TAX exécuté en X 16 bits juste après un LDA 8 bits,
        # transférant un octet haut résiduel (B) en plus de l'id
        # personnage, produisant un index de table hors limites ; (2)
        # lecture de la table de couleurs en adressage absolu court
        # (dépendant de DBR, qui vaut \$7E à cet endroit de la routine
        # vanilla, confirmé par désassemblage) au lieu d'absolu long
        # (banque C3 explicite). Voir le commentaire détaillé dans
        # mod_stat_colors() pour la preuve complète -- ce mécanisme n'a
        # plus été retouché depuis. Système à 5 couleurs maintenant actif
        # (rouge/jaune/blanc/vert/cyan), les 3 nouvelles palettes
        # (rouge/jaune/vert) étant créées dans la WRAM \$7E3049 selon la
        # méthode de BC ("yellow_palette"), voir mod_stat_colors().
        self.mod_stat_colors()
