# lcal

A simple terminal calendar application with timezone support, event management, and a configurable TUI.

## Installation

```
pip install .
```

Or directly from the source directory:

```
pip install -e .
```

## Usage

```
lcal [OPTIONS]
```

### Options

| Flag | Description |
|------|-------------|
| `-l`, `--list-timezones` | Print all available IANA timezone names and exit |
| `-t TZ`, `--set-timezone TZ` | Persist a new display timezone to the config file and exit |

## Key Bindings (default)

All key bindings can be customised in the configuration file (see below).

### Global

| Key | Action |
|-----|--------|
| `Tab` | Toggle focus between the calendar and the sidebar |
| `q` | Quit |
| `g` | Go to a specific date |
| `z` | Change the display timezone |

### Calendar view

| Key | Action |
|-----|--------|
| `h` / `←` | Move cursor left (previous day) |
| `l` / `→` | Move cursor right (next day) |
| `j` / `↓` | Move cursor down (next week) |
| `k` / `↑` | Move cursor up (previous week) |
| `t` | Jump to today |
| `n` | Next month |
| `p` | Previous month |
| `a` | Add an event on the selected day |
| `i` | Enter event-selection mode for the selected day |

### Event-selection mode

| Key | Action |
|-----|--------|
| `Esc` | Exit event-selection mode |
| `j` / `↓` | Select next event |
| `k` / `↑` | Select previous event |
| `e` | Edit the selected event (name, start time, end time, colour, or move) |
| `d` | Delete the selected event |
| `n` | Edit the description of the selected event |

When editing (`e`), an additional sub-prompt is shown:

| Sub-key | Action |
|---------|--------|
| `s` | Edit start time |
| `e` | Edit end time |
| `n` | Edit event name |
| `c` | Edit colour |
| `m` | Move event to a different date |

### Sidebar (TODO list)

| Key | Action |
|-----|--------|
| `j` / `↓` | Move todo cursor down |
| `k` / `↑` | Move todo cursor up |
| `a` | Add a new todo item |
| `e` | Edit the selected todo item |
| `n` | Open the selected todo's note file in `$EDITOR` |
| `d` | Delete the selected todo item |
| `+` / `=` | Increase priority |
| `-` | Decrease priority |

## Configuration

The configuration file is located at `~/.config/lcal/config.py` and is a plain Python file. It is created automatically with sensible defaults on the first run.

### Example config

```python
ics_path = '/home/user/.config/lcal/calendar.ics'
timezone = 'Europe/London'
show_timezone = True
show_day_borders = True
first_weekday = 7        # 1=Monday … 7=Sunday
sidebar_ratio = 0.2
notes_extension = 'md'
show_events_tab = True
holidays_ics_path = '/home/user/.config/lcal/holidays.ics'
holiday_colour = 'COLOR_RED'

# Time format: True = 24-hour (14:30), False = 12-hour (02:30PM)
time_24h = True

# Input date format for the "go to date" prompt.
# Supported values: 'dd/mm/yyyy', 'mm/dd/yyyy', 'yyyy/mm/dd', 'yyyy-mm-dd'
date_format = 'dd/mm/yyyy'

# strftime format string used to display the date label in the Events tab.
# Examples: '%a %d %b %Y'  →  Mon 01 Jan 2024
#           '%Y-%m-%d'     →  2024-01-01
event_date_format = '%a %d %b %Y'

# Editor command for opening event descriptions and todo notes.
# Falls back to the EDITOR environment variable, then vim.
editor = None  # e.g. 'nano', 'nvim', 'micro'

# Insert a blank spacer line between the day number and events in the day cell.
event_spacing = True

# Fraction of the sidebar height occupied by the Events tab (0.0–1.0).
events_tab_ratio = 0.5

day_names = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
month_names = [
    'January', 'February', 'March', 'April', 'May', 'June',
    'July', 'August', 'September', 'October', 'November', 'December',
]

colours = {
    'cursor': ['COLOR_CYAN', -1],
    'header': ['COLOR_WHITE', -1],
    'weekend': ['COLOR_YELLOW', -1],
    'today': ['COLOR_GREEN', -1],
    'accent': ['COLOR_CYAN', -1],
}

# Customise key bindings. Each value is a single character string.
keybindings = {
    'quit': 'q',
    'goto_date': 'g',
    'change_timezone': 'z',
    'go_today': 't',
    'next_month': 'n',
    'prev_month': 'p',
    'add_event': 'a',
    'enter_event_selection': 'i',
    'edit_event': 'e',
    'delete_event': 'd',
    'edit_description': 'n',
    'move_up': 'k',
    'move_down': 'j',
    'move_left': 'h',
    'move_right': 'l',
    'todo_add': 'a',
    'todo_edit': 'e',
    'todo_open': 'n',
    'todo_delete': 'd',
    'todo_priority_up': '=',
    'todo_priority_down': '-',
}
```

### Configuration reference

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `ics_path` | str | `~/.config/lcal/calendar.ics` | Path to the primary ICS calendar file |
| `timezone` | str | `Etc/UTC` | IANA timezone used for displaying and entering event times |
| `show_timezone` | bool | `True` | Show the current timezone in the calendar header |
| `show_day_borders` | bool | `True` | Draw borders between calendar cells |
| `first_weekday` | int | `7` | First day of the week (1=Mon … 7=Sun) |
| `sidebar_ratio` | float | `0.2` | Fraction of terminal width used by the sidebar |
| `notes_extension` | str | `md` | File extension for event descriptions and todo notes |
| `show_events_tab` | bool | `True` | Show the Events section in the sidebar |
| `holidays_ics_path` | str | `~/.config/lcal/holidays.ics` | Path to a read-only holidays ICS file |
| `holiday_colour` | str | `COLOR_RED` | Colour used to highlight holidays |
| `time_24h` | bool | `True` | `True` for 24-hour clock, `False` for 12-hour (AM/PM) |
| `date_format` | str | `dd/mm/yyyy` | Date format for the "go to date" prompt (`dd/mm/yyyy`, `mm/dd/yyyy`, `yyyy/mm/dd`, `yyyy-mm-dd`) |
| `event_date_format` | str | `%a %d %b %Y` | strftime format string for the date label in the Events tab |
| `editor` | str | `None` | Editor command used to open event descriptions and todo notes (e.g. `nano`, `nvim`). Falls back to the `EDITOR` environment variable, then `vim`. |
| `event_spacing` | bool | `True` | Insert a blank line between the day number and the first event, and between consecutive events in the day cell |
| `events_tab_ratio` | float | `0.5` | Fraction of the sidebar height occupied by the Events tab (0.0–1.0) |
| `day_names` | list | English abbreviations | List of 7 day name strings starting from Monday |
| `month_names` | list | English names | List of 12 month name strings |
| `colours` | dict | See above | Colour pairs for UI elements |
| `keybindings` | dict | See above | Map of action names to single-character keys |

## Data files

| File | Description |
|------|-------------|
| `~/.config/lcal/calendar.ics` | Main event store (iCalendar format) |
| `~/.config/lcal/holidays.ics` | Optional read-only holiday calendar |
| `~/.config/lcal/todo/` | Directory containing todo/note files |

## Adding events

Press `a` on a calendar day to add an event:

1. Enter a start time (`HH:MM` or `HHMM`), or press Enter for an all-day event.
2. Enter an end time (same format), or press Enter to skip. The end time must be strictly after the start time.
3. Enter the event name.
4. Choose an optional colour.

## Holidays

To display public holidays, point `holidays_ics_path` at a local ICS file.  Many countries publish official holiday calendars in ICS format that can be downloaded from providers such as <https://www.officeholidays.com>.

## Timezones

lcal stores all timed events with full timezone information.  Use `z` inside the app or `lcal --set-timezone IANA/Zone` on the command line to change the display timezone.  Run `lcal --list-timezones` to see all valid IANA zone names.
