import os

CONFIG_DIR = os.path.expanduser("~/.config/lcal")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.py")

TODO_DIR = os.path.join(CONFIG_DIR, "todo") # path to store todo files

DEFAULT_TIMEZONE = "Etc/UTC"

DEFAULT_CONFIG = {
    "ics_path": os.path.join(CONFIG_DIR, "calendar.ics"),
    "timezone": DEFAULT_TIMEZONE,
    "show_timezone": True,
    "show_day_borders": True,
    "first_weekday": 7,
    "sidebar_ratio": 0.2,
    "notes_extension": "md",
    "show_events_tab": True,
    "holidays_ics_path": os.path.join(CONFIG_DIR, "holidays.ics"),
    "holiday_colour": "COLOR_RED",
    "time_24h": True,
    "date_format": "dd/mm/yyyy",
    "event_date_format": "%a %d %b %Y",
    "editor": 'vi',
    "event_spacing": True,
    "events_tab_ratio": 0.6,
    "day_names": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
    "month_names": [
        "January", "February", "March", "April", "May", "June",
        "July", "August", "September", "October", "November", "December",
    ],
    "colours": {
        "cursor": ["COLOR_CYAN", -1],
        "header": ["COLOR_WHITE", -1],
        "weekend": ["COLOR_YELLOW", -1],
        "today": ["COLOR_GREEN", -1],
        "accent": ["COLOR_CYAN", -1],
    },
    "keybindings": {
        "quit": "q",
        "goto_date": "g",
        "change_timezone": "z",
        "go_today": "t",
        "next_month": "n",
        "prev_month": "p",
        "add_event": "a",
        "enter_event_selection": "i",
        "edit_event": "e",
        "delete_event": "d",
        "edit_description": "n",
        "move_up": "k",
        "move_down": "j",
        "move_left": "h",
        "move_right": "l",
        "todo_add": "a",
        "todo_edit": "e",
        "todo_open": "n",
        "todo_delete": "d",
        "todo_priority_up": "=",
        "todo_priority_down": "-",
    },
}


def load_config():
    # Load configuration from file
    os.makedirs(CONFIG_DIR, exist_ok=True)
    if os.path.exists(CONFIG_FILE):
        config = {}
        with open(CONFIG_FILE) as f:
            exec(f.read(), {}, config)
        return config
    else:
        # Create config file if it doesn't exist
        save_config(DEFAULT_CONFIG)
        return DEFAULT_CONFIG


def _format_config_value(val, indent=0):
    # Format indentation of the config file as a python file
    ind = "    " * indent
    if isinstance(val, dict):
        if not val:
            return "{}"
        lines = ["{"]
        for k, v in val.items():
            formatted = _format_config_value(v, indent + 1)
            lines.append(f"{ind}    {repr(k)}: {formatted},")
        lines.append(f"{ind}}}")
        return "\n".join(lines)
    elif isinstance(val, list):
        if not val:
            return "[]"
        # Inline list for less than 80 chars
        if all(isinstance(item, (str, int, float, bool, type(None))) for item in val):
            inline = repr(val)
            if len(inline) <= 80:
                return inline
        # Multiline for long or nested lists
        lines = ["["]
        for item in val:
            formatted = _format_config_value(item, indent + 1)
            lines.append(f"{ind}    {formatted},")
        lines.append(f"{ind}]")
        return "\n".join(lines)
    else:
        return repr(val)


def save_config(config):
    # Save configuration to file
    with open(CONFIG_FILE, "w") as f:
        for key in DEFAULT_CONFIG:
            if key in config:
                f.write(f"{key} = {_format_config_value(config[key])}\n")


def init_ics_file():
    # Initialise the ICS file in the config directory
    config = load_config()
    ics_path = config["ics_path"]
    if not os.path.exists(ics_path):
        # Create an empty ICS file
        with open(ics_path, "w") as f:
            f.write("BEGIN:VCALENDAR\nVERSION:2.0\nEND:VCALENDAR\n")
