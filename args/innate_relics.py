def name():
    return "Innate Relics"

def parse(parser):
    innate_relics = parser.add_argument_group("Innate Relics")

    innate_relics.add_argument("-rir", "--random-innate-relics", default = 0, type = int,
                                choices = range(0, 101), metavar = "PERCENT",
                                help = "each of the 14 playable characters independently has a "
                                       "%(metavar)s%% chance (0-100) of starting with a random relic's "
                                       "effects innately, in addition to their 2 normal relic slots. "
                                       "The number of characters who actually get one can vary from "
                                       "seed to seed. 0 (default) disables this entirely; 100 guarantees "
                                       "every character gets one.")

def process(args):
    pass

def flags(args):
    flags = ""

    if args.random_innate_relics:
        flags += f" -rir {args.random_innate_relics}"

    return flags

def options(args):
    return [
        ("Innate Relics", args.random_innate_relics, "random_innate_relics"),
    ]

def menu(args):
    return (name(), options(args))

def log(args):
    from log import format_option
    log = [name()]

    for entry in options(args):
        log.append(format_option(*entry))

    return log
