import curses
import os
import argparse

from lcal.calendar_ui import CalendarApp
from lcal.config import init_ics_file


def get_parser():
    parser = argparse.ArgumentParser(prog="lcal", description="A very simple tui calendar with timezone support")

    parser.add_argument("-l", "--list-timezones", action="store_true",
                        help="List available timezones")

    parser.add_argument("-t", "--set-timezone", type=str, default=None,
                        help="Set current timezone")

    return parser


def main():
    args = get_parser().parse_args()

    if args.list_timezones:
        from zoneinfo import available_timezones
        timezones = available_timezones()
        # List available timezones in alphabetical order
        for tz in sorted(timezones):
            print(tz)
        return
    if args.set_timezone is not None:
        from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
        try:
            ZoneInfo(args.set_timezone)
            from lcal.config import load_config, save_config
            # Save the given timezone in config file
            config = load_config()
            timezone = config["timezone"]
            config["timezone"] = args.set_timezone
            save_config(config)
        # Stop if given string is not an available timezone
        except (ZoneInfoNotFoundError, KeyError):
            print("Not an available zone name")
            print("Use lcal -l to list available timezones")
            return

    # Initialise and run the calendar application
    init_ics_file()

    # Validate the timezone from the config file before starting curses
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
    from lcal.config import load_config
    _cfg = load_config()
    _tz = _cfg.get("timezone", "Etc/UTC")
    try:
        ZoneInfo(_tz)
    except (ZoneInfoNotFoundError, KeyError):
        print(f"Invalid timezone in config: {_tz!r}")
        print("Use lcal -l to list available timezones")
        print("Use lcal -t <timezone> to set the correct timezone")
        return

    # Reduce ESC key delay
    os.environ.setdefault("ESCDELAY", "25")

    app = CalendarApp()
    curses.wrapper(app.run)


if __name__ == "__main__":
    main()
