def name():
    return "Skill Pools"

def parse(parser):
    skill_pools = parser.add_argument_group("Skill Pools")
    skill_pools.add_argument("-rsk", "--randomize-skills", action = "store_true",
        help = "Randomize what commands like Rage/Blitz/SwdTech/Dance/... actually do (portage de Beyond Chaos)")
    skill_pools.add_argument("-rskc", "--randomize-skills-chance", type = float, default = 0.5,
        help = "Chance (0.0-1.0) for each eligible command to be replaced (default 0.5)")

def process(args):
    pass

def flags(args):
    flags = ""

    if args.randomize_skills:
        flags += " -rsk"
        if args.randomize_skills_chance != 0.5:
            flags += f" -rskc {args.randomize_skills_chance}"

    return flags

def options(args):
    return [
        ("Randomize Skills", args.randomize_skills, "randomize_skills"),
        ("Randomize Skills Chance", args.randomize_skills_chance, "randomize_skills_chance"),
    ]

def menu(args):
    return (name(), options(args))

def log(args):
    from log import format_option
    log = [name()]

    for entry in options(args):
        log.append(format_option(*entry))

    return log
