# lcal

A simple TUI calendar app with timezone support, event/todo management and no dependencies outside of python standard library.

## Installation

```sh
pip install .
```

## Getting Started

### Timezone

Remember to set your timezone for your first run. To see all available IANA timezone.

```sh
lcal -l # or --list-timezone
```

Then set the timezone.

```sh
lcal -t [TZ] # or --set-timezone [TZ]
```

### Holidays

To display public holidays, point `holidays_ics_path` at a local iCalendar file.  Many countries publish official holiday calendars in iCalendar format that can be downloaded from <https://www.officeholidays.com/countries>. Go to the website, choose the country you live in, click "Subscribe to Calendar", then open the link given in the page, the iCalendar file will be downloaded.

## Key Bindings (default)

All key bindings can be customised in the configuration file.

### Global

| Key | Action |
|-----|--------|
| `Tab` | Toggle focus between the calendar and TODO box |
| `q` | Quit |
| `g` | Go to a specific date |
| `z` | Change timezone |

### Calendar view

| Key | Action |
|-----|--------|
| `h` / `←` | Move to previous day |
| `l` / `→` | Move to next day |
| `j` / `↓` | Move to next week |
| `k` / `↑` | Move to previous week |
| `t` | Jump to today |
| `n` | Move to next month |
| `p` | Move to previous month |
| `a` | Add an event on the selected day |
| `i` | Enter event-selection mode |

### Event-selection mode

| Key | Action |
|-----|--------|
| `Esc` / `Ctrl+[` | Exit event-selection mode |
| `j` / `↓` | Select next event |
| `k` / `↑` | Select previous event |
| `e` | Edit the selected event |
| `d` | Delete the selected event |
| `n` | Edit the description of the selected event |

When editing (`e`), an additional sub-prompt is shown:

| Sub-key | Action |
|---------|--------|
| `s` | Edit start time |
| `e` | Edit end time |
| `n` | Edit event name |
| `c` | Edit colour |
| `m` | Move event to a specific date |

When deleting (`d`) an event with description, an additional sub-prompt is show, deleting only the description can be chosen by (`d`).

### Sidebar (TODO list)

| Key | Action |
|-----|--------|
| `j` / `↓` | Move todo cursor down |
| `k` / `↑` | Move todo cursor up |
| `a` | Add a new todo item |
| `e` | Edit the selected todo item |
| `n` | Edit the selected todo's note |
| `d` | Delete the selected todo item |
| `=` | Increase priority value |
| `-` | Decrease priority value |

When editing (`e`), an additional sub-prompt is shown:

| Sub-key | Action |
|---------|--------|
| `p` | Edit priority |
| `n` | Edit todo name |
| `c` | Edit colour |

## Configuration

The configuration file is located at `~/.config/lcal/config.py` and is created automatically on the first run.

### Configuration reference

| Key | Type | Description |
|-----|------|-------------|
| `ics_path` | str | Path to the iCalendar file |
| `timezone` | str | IANA timezone used for displaying and entering event times |
| `show_timezone` | bool | Show the current timezone in the calendar header |
| `show_day_borders` | bool | Draw borders between calendar cells |
| `first_weekday` | int | First day of the week (1=Mon … 7=Sun) |
| `sidebar_ratio` | float | Fraction of terminal width used by the sidebar |
| `notes_extension` | str | File extension for event descriptions and todo notes |
| `show_events_tab` | bool | Show the Events section in the sidebar |
| `holidays_ics_path` | str | Path to a read-only holidays ICS file |
| `holiday_colour` | str | Colour used to highlight holidays |
| `time_24h` | bool | `True` for 24-hour clock, `False` for 12-hour (AM/PM) |
| `date_format` | str | Date format for the "go to date" prompt (`dd/mm/yyyy`, `mm/dd/yyyy`, `yyyy/mm/dd`, `yyyy-mm-dd`) |
| `event_date_format` | str | strftime format string for the date label in the Events tab |
| `editor` | str | Editor command used to open event descriptions and todo notes (e.g. `nano`, `nvim`). Falls back to the `EDITOR` environment variable, then `vim`. |
| `event_spacing` | bool | Insert a blank line between the day number and the first event, and between consecutive events in the day cell |
| `events_tab_ratio` | float | Fraction of the sidebar height occupied by the Events tab (0.0–1.0) |
| `day_names` | list | List of 7 day name strings starting from Monday |
| `month_names` | list | List of 12 month name strings |
| `colours` | dict | Colour pairs for UI elements |
| `keybindings` | dict | Map of action names to single-character keys |
