import curses

# Default colour pairs: each entry is [fg_colour_name, bg_colour_name]
# Colour names must match curses constants (e.g. "COLOR_CYAN") or -1
DEFAULT_COLOURS = {
    "cursor": ["COLOR_YELLOW", -1],
    "header": ["COLOR_WHITE", -1],
    "weekend": ["COLOR_RED", -1],
    "today": ["COLOR_GREEN", -1],
    "cursor_day": ["COLOR_WHITE", -1],
    "accent": ["COLOR_CYAN", -1],
}

# Colour pairs 6–13 are reserved for event colours (one per curses colour).
# Each pair uses the named colour as foreground on the default background.
EVENT_COLOUR_PAIRS = {
    "COLOR_BLACK": 6,
    "COLOR_RED": 7,
    "COLOR_GREEN": 8,
    "COLOR_YELLOW": 9,
    "COLOR_BLUE": 10,
    "COLOR_MAGENTA": 11,
    "COLOR_CYAN": 12,
    "COLOR_WHITE": 13,
}


def _resolve_colour(val):
    # Resolve a colour string name or int to a curses colour integer
    if isinstance(val, int):
        return val
    if isinstance(val, str):
        return getattr(curses, val, -1)
    return -1


def init_colours(config):
    # Initialize curses colour pairs from config.
    colours = {**DEFAULT_COLOURS, **config.get("colours", {})}
    for pair_num, key in [
        (1, "cursor"),
        (2, "header"),
        (3, "weekend"),
        (4, "today"),
        (5, "cursor_day"),
        (14, "accent"),
    ]:
        entry = colours.get(key, DEFAULT_COLOURS[key])
        fg = _resolve_colour(entry[0])
        bg = _resolve_colour(entry[1])
        curses.init_pair(pair_num, fg, bg)

    # Initialize event colour pairs (6–13), one per curses colour.
    for colour_name, pair_num in EVENT_COLOUR_PAIRS.items():
        fg = getattr(curses, colour_name, -1)
        curses.init_pair(pair_num, fg, -1)
