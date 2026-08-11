## FF6 Worlds Beyond (Worlds Collide + Beyond Chaos)

An experimental project exploring the integration of Beyond Chaos-style random skill mechanics (and more) into Final Fantasy VI: Worlds Collide.

The goal is to combine the randomizer framework and gameplay systems of Worlds Collide with Beyond Chaos' approach to randomized abilities, allowing character commands to be replaced by a much larger pool of randomized skills.

The project is still experimental and actively being refined. Balancing, additional customization options, compatibility with other flags, and further randomization features are all ongoing areas of development.

### New Features

#### Innate Relics — `-rir`

Added support for **Innate Relics**, allowing characters to receive a randomly selected relic that grants its normal relic effect innately.

Usage:

* `-rir 100` → every character has a 100% chance to receive an Innate Relic.
* `-rir 50` → each character has an independent 50% chance.
* `-rir 0` → no Innate Relics.

The assigned relics are displayed in the Status Menu.

#### Randomize Skills — `-rsk`

Added the ability to randomize character skill sets.

`-rsk` pulls random skills from the full skill pool of the game (254 skills). The pool now includes Esper summons, SwdTech/Blitz techniques, Lores, Rages, Dances, and more. 

#### Character Stat Colors — `-csrp`

Added optional **character stat color randomization**.

Usage:

* `-csrp MIN MAX`

This applies random colors to character stats based on the specified percentage range.

The feature is **disabled by default** and only activates when `-csrp` is explicitly provided.

#### Item Rarity Markers — `-irm`

Added optional **item rarity markers**.

`-irm` marks rare items with `!` / `!!` indicators, making it easier to identify valuable or particularly rare equipment and items during a seed.

The rarity markers are cosmetic and do not alter the underlying item IDs or functionality.


Credits :

This project builds upon the work of the original Worlds Collide and Beyond Chaos projects.

Full credit for the original projects, code, and ideas belongs to their respective authors and contributors.

This repository is an experimental extension/integration and is not affiliated with or an official release of either project.

Status :

Work in progress. Things may break. Probably occasionally in spectacular ways.

The goal is to eventually provide something stable enough for others to experiment with, test, and provide feedback on.


## Links

###### Start playing: [ff6worldscollide.com](https://www.ff6worldscollide.com)
###### More Info: [wiki.ff6worldscollide.com](https://wiki.ff6worldscollide.com)
###### Community: [discord](https://discord.gg/5MPeng5)

## Usage

```sh
$ python3 wc.py -i ffiii.smc
```

```sh
$ python3 wc.py -h
```

