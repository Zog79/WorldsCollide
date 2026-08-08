def name():
    return "Skill Pools"

def parse(parser):
    skill_pools = parser.add_argument_group("Skill Pools")
    skill_pools.add_argument("-rsk", "--randomize-skills", action = "store_true",
        help = "Randomize what commands like Rage/Blitz/SwdTech/Dance/... actually do (portage de Beyond Chaos), structure par personnage : slot1=Fight ou Magic, slot2=logique native WC, slot3=100% aleatoire, slot4=Item ou aleatoire")
    skill_pools.add_argument("-rskm", "--randomize-skills-magic-chance", type = float, default = 0.5,
        help = "Chance (0.0-1.0) that slot 1 gets Magic instead of Fight (default 0.5)")
    skill_pools.add_argument("-rskv", "--randomize-skills-vanilla-chance", type = float, default = 0.5,
        help = "Chance (0.0-1.0) that slot 4 gets Item (instead of random) (default 0.5)")

def process(args):
    pass

def flags(args):
    flags = ""

    if args.randomize_skills:
        flags += " -rsk"
        if args.randomize_skills_magic_chance != 0.5:
            flags += f" -rskm {args.randomize_skills_magic_chance}"
        if args.randomize_skills_vanilla_chance != 0.5:
            flags += f" -rskv {args.randomize_skills_vanilla_chance}"

    return flags

def options(args):
    return [
        ("Randomize Skills", args.randomize_skills, "randomize_skills"),
        ("Randomize Skills Magic Chance", args.randomize_skills_magic_chance, "randomize_skills_magic_chance"),
        ("Randomize Skills Vanilla Chance", args.randomize_skills_vanilla_chance, "randomize_skills_vanilla_chance"),
    ]

def menu(args):
    return (name(), options(args))

def log(args):
    from log import format_option
    log = [name()]

    for entry in options(args):
        log.append(format_option(*entry))

    return log
