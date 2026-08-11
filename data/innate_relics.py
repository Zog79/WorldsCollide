import random

from memory.space import Bank, Reserve, Write, Read
import instruction.asm as asm

from data.items import Items


class InnateRelics:
    # Beyond Chaos "Memento Mori" relic pool (BeyondChaosRandomizer/BeyondChaos/patches.py::hidden_relic(),
    # relic_list / rare_relic_list), ported here by vanilla item name rather than raw id so the pool stays
    # readable and self-documenting.
    #
    # "Rage Ring" and "Blizzard Orb" are intentionally left out of the rare pool for this first version.
    # Beyond Chaos gives both of them dedicated extra hooks that check every one of a character's relics
    # (equipped AND innate) whenever their special vanilla behavior triggers -- that isn't ported here.
    # Without those hooks, a character whose only copy of Rage Ring/Blizzard Orb is the innate one would
    # still get its ordinary stat/status effects (handled generically below), but not the item's special
    # behavior, which could look like a bug rather than a known limitation. Excluding them avoids that.
    COMMON_RELIC_NAMES = [
        "Goggles", "Star Pendant", "Peace Ring", "Amulet", "White Cape", "Jewel Ring", "Fairy Ring",
        "Barrier Ring", "MithrilGlove", "Guard Ring", "RunningShoes", "Wall Ring", "Cherub Down", "Cure Ring",
        "True Knight", "Zephyr Cape", "Czarina Ring", "Cursed Ring", "Earrings", "Atlas Armlet", "Sneak Ring",
        "Hero Ring", "Crystal Orb", "Gold Hairpin", "Gauntlet", "Hyper Wrist", "Beads", "Black Belt",
        "Dragon Horn", "Back Guard", "Gale Hairpin", "Sniper Sight", "Tintinabar", "Sprint Shoes",
    ]
    RARE_RELIC_NAMES = [
        "Offering", "Merit Award", "Economizer", "Marvel Shoes", "Safety Bit", "Memento Ring", "Ribbon",
        "Moogle Charm", "Charm Bangle", "Genji Glove", "Exp. Egg", "Relic Ring", "Pod Bracelet", "Muscle Belt",
    ]
    RARE_CHANCE_DENOMINATOR = 10  # 1 in 10 chance of a rare relic, same odds as Beyond Chaos

    # Vanilla routine $C2/0E77 ("equipment check function") computes one entity's battle stats.
    # BUG FIX (see chat): the hook used to sit at $C2/0E9A, the address Beyond Chaos's own hidden
    # relic patch uses. At that exact point, A does NOT hold the character id -- it holds the
    # character's *sprite* ("C2/0E97: LDA $15DB,X (get sprite, which doubles as character index??)",
    # confirmed against a public FF6 disassembly, comment and all). That only coincides with the
    # character id when nobody's sprite has been reassigned -- not a safe assumption in a randomizer
    # that can shuffle character sprites. Using it as a table index applied the wrong (or out of
    # range) relic to characters on every stat recalculation, including at party creation --
    # matching the black-screen/graphical corruption seen right at New Game.
    #
    # The real, unmodified character id is available 16 bytes earlier, before the game reuses A to
    # look up the sprite:
    #   C2/0E7D: PHA
    #   C2/0E7E: AND #$0F   <- masked character id (0-15), still A when PLA restores it below
    #   ...
    #   C2/0E84: PLA        <- same masked character id, now DBR is back to normal
    #   (unrelated: LDX #$3E / STZ $11A0,X loop clearing scratch memory -- A untouched)
    #   C2/0E8D: INC A      <- from HERE ONWARD A stops being the character id (turned into the
    #   C2/0E8E: XBA           sprite-table lookup index instead)
    #   C2/0E8F: LDA #$25
    # So the hook now sits at $C2/0E8D, the last point where A is still guaranteed to be the real
    # character id, confirmed present/unpatched in the reference rom used to design this hook and
    # unmodified anywhere else in this codebase.
    HOOK_ADDRESS = 0x20e8d

    # bytes actually overwritten in place by our JSR: INC A (1) ; XBA (1) ; LDA #$25 (2).
    # everything else in this vanilla routine -- including the loop that applies every equipment slot's
    # properties (both normal relic slots included) via APPLY_ITEM_PROPERTIES further down -- is left
    # completely untouched, immediately after our JSR returns.
    HOOK_LENGTH = 4

    # local subroutine in bank C2, never touched by WC, that applies one equipment item's properties to
    # the character currently being processed. this is the exact same routine vanilla itself calls once
    # per equipment slot right after this hook -- reused here instead of reimplemented.
    APPLY_ITEM_PROPERTIES = 0x0f9a

    def __init__(self, rom, args, characters, items):
        self.rom = rom
        self.args = args
        self.characters = characters
        self.items = items

        # character.id -> item id of that character's innate relic (only characters that received one)
        self.relic_assignments = {}

    def relic_pool(self):
        common = [self.items.get_id(name) for name in self.COMMON_RELIC_NAMES]
        rare = [self.items.get_id(name) for name in self.RARE_RELIC_NAMES]
        return common, rare

    def assign(self):
        # per-character independent probability (user direction, replacing the earlier "fixed count of
        # characters" model): each of the 14 playable characters is rolled separately against `percent`,
        # so the final number of characters with a relic varies from seed to seed. 100 -> every character
        # (equivalent to a guaranteed roll for each), 0 -> none (mod() already returns before calling
        # this in that case, but the loop below would naturally select nobody either way).
        percent = self.args.random_innate_relics
        if not percent:
            return

        common_pool, rare_pool = self.relic_pool()

        for character in self.characters.playable:
            if random.randint(1, 100) > percent:
                continue

            if random.randint(1, self.RARE_CHANCE_DENOMINATOR) == self.RARE_CHANCE_DENOMINATOR:
                item_id = random.choice(rare_pool)
            else:
                item_id = random.choice(common_pool)
            self.relic_assignments[character.id] = item_id

    def write_combat_hook(self):
        if not self.relic_assignments:
            return

        # fixed-size table, one byte per playable character, EMPTY (0xff) = no innate relic --
        # independent of how many characters actually received one this seed
        relic_table = [Items.EMPTY] * self.characters.CHARACTER_COUNT
        for character_id, item_id in self.relic_assignments.items():
            relic_table[character_id] = item_id
        table = Write(Bank.C2, relic_table, "innate relics: character -> relic table")

        # captured directly from the rom being processed (not transcribed by hand) -- these are the only
        # 3 bytes our hook actually overwrites at HOOK_ADDRESS
        original_bytes = Read(self.HOOK_ADDRESS, self.HOOK_ADDRESS + self.HOOK_LENGTH - 1)

        hook_code = [
            asm.PHP(),                                            # save caller's A/X width (M/X flags) --
                                                                    # 8-bit A/X/Y here (SEP #$30 earlier in
                                                                    # this routine, confirmed by disassembly)
            asm.PHA(),                                            # save character id (confirmed in A at
                                                                    # this exact point, see class docstring)
            asm.XY8(),                                            # (already 8-bit here; kept so this hook
                                                                    # stays correct even if the hook point
                                                                    # ever moves again) force 8-bit X so TAX
                                                                    # can't pull in a stale high byte
            asm.TAX(),                                            # x = character id (0-13)
            asm.LDA(table.start_address_snes, asm.LNG_X),          # a = this character's innate relic id.
                                                                    # long addressing (bank explicit) since
                                                                    # DBR is not guaranteed to be C2 here
            asm.PHA(),                                             # stash the relic id
            asm.XY16(),                                            # APPLY_ITEM_PROPERTIES needs 16-bit X
                                                                    # (it does item_id*30 via TAX on a 16-bit
                                                                    # product -- 8-bit X would truncate it for
                                                                    # any item id above ~8). Explicit, not
                                                                    # inherited from the caller's ambient
                                                                    # state, since that state now differs
                                                                    # from what it was at the old hook point.
            asm.PLA(),                                             # relic id back into a
            asm.JSR(self.APPLY_ITEM_PROPERTIES, asm.ABS),          # same routine vanilla uses for every
                                                                    # equipment slot; 0xff (empty) is already
                                                                    # handled safely by it, same as an empty
                                                                    # vanilla relic slot
            asm.PLA(),                                             # restore character id
            asm.PLP(),                                             # restore the ORIGINAL 8-bit A/X/Y before
                                                                    # falling back into vanilla code that
                                                                    # expects it (APPLY_ITEM_PROPERTIES
                                                                    # itself doesn't touch X/Y width, so this
                                                                    # is genuinely needed here, unlike M which
                                                                    # it already restores on its own)
            original_bytes,                                        # replay the 4 vanilla bytes we overwrote
                                                                    # (INC A ; XBA ; LDA #$25)
            asm.RTS(),
        ]
        space = Write(Bank.C2, hook_code, "innate relics: combat hook")

        # HOOK_LENGTH (4) is 1 byte larger than the JSR itself (3) -- the leftover byte MUST be a NOP,
        # not left as whatever ROM byte happened to be there: our RTS lands exactly on it (JSR/RTS always
        # returns right after the JSR instruction, regardless of how big the reserved region is), so if
        # it weren't a harmless NOP it would be executed as a bogus opcode before falling through to the
        # untouched vanilla continuation.
        hook = Reserve(self.HOOK_ADDRESS, self.HOOK_ADDRESS + self.HOOK_LENGTH - 1,
                        "innate relics: combat hook (redirect)", asm.NOP())
        hook.write(
            asm.JSR(space.start_address, asm.ABS),
        )

    def mod(self):
        if not self.args.random_innate_relics:
            return

        self.assign()
        self.write_combat_hook()

    def log(self):
        from log import section

        lines = []
        for character in self.characters.playable:
            if character.id not in self.relic_assignments:
                continue
            item_id = self.relic_assignments[character.id]
            lines.append(f"{character.name:<8} {self.items.get_name(item_id)}")

        if lines:
            section("Innate Relics", lines, [])

    def write(self):
        if self.args.spoiler_log:
            self.log()
