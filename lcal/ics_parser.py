from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from lcal.events import Event
from lcal.config import DEFAULT_TIMEZONE


def parse_ics(filepath):
    # Parse ics file and return a list of Event objects
    events = []
    with open(filepath, "r") as f:
        lines = f.readlines()

    in_event = False
    summary = ""
    dtstart = None
    dtend = None
    timezone = DEFAULT_TIMEZONE
    colour = None
    description = None

    for line in lines:
        line = line.strip()
        if line == "BEGIN:VEVENT":
            in_event = True
            summary = ""
            dtstart = None
            dtend = None
            timezone = DEFAULT_TIMEZONE
            colour = None
            description = None
        elif line == "END:VEVENT":
            if dtstart is not None:
                events.append(Event(summary, dtstart, dtend, timezone, colour,
                                    description))
            in_event = False
        elif in_event:
            if line.startswith("SUMMARY:"):
                summary = line[len("SUMMARY:"):]
            elif line.startswith("DTSTART"):
                dtstart, timezone = _parse_dt(line)
            elif line.startswith("DTEND"):
                dtend, _ = _parse_dt(line)
            elif line.startswith("COLOR:"):
                colour = f'COLOR_{line[len("COLOR:"):].upper().strip()}'
            elif line.startswith("DESCRIPTION:"):
                description = line[len("DESCRIPTION:"):].replace("\\n", "\n")

    return events


def _parse_dt(line):
    # Parse a DTSTART or DTEND line and return datetime and timezone
    timezone = DEFAULT_TIMEZONE
    if "VALUE=DATE" in line:
        # All-day event: DTSTART;VALUE=DATE:yyyymmdd
        parts = line.split(":")
        dt_str = parts[1] if len(parts) > 1 else ""
        return datetime.strptime(dt_str, "%Y%m%d").date(), timezone
    elif "TZID=" in line:
        # Format: DTSTART;TZID=Etc/UTC:yyyymmddThhmmss
        parts = line.split(":")
        tz_part = parts[0]
        dt_str = parts[1] if len(parts) > 1 else ""
        tz_start = tz_part.find("TZID=")
        if tz_start != -1:
            timezone = tz_part[tz_start + 5:]
    else:
        # Format: DTSTART:yyyymmddThhmmss
        parts = line.split(":")
        dt_str = parts[1] if len(parts) > 1 else ""

    dt = datetime.strptime(dt_str, "%Y%m%dT%H%M%S")
    # Return date time after considering timezone
    try:
        dt = dt.replace(tzinfo=ZoneInfo(timezone))
    except (ZoneInfoNotFoundError, KeyError):
        pass
    return dt, timezone


def write_ics(filepath, events):
    # Write a list of Event objects to an ICS file
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0"]
    for event in events:
        lines.append("BEGIN:VEVENT")
        tz = event.timezone
        if event.is_all_day():
            lines.append(f"DTSTART;VALUE=DATE:{event.dtstart.strftime('%Y%m%d')}")
        else:
            lines.append(f"DTSTART;TZID={tz}:{event.dtstart.strftime('%Y%m%dT%H%M%S')}")
            if event.dtend:
                lines.append(f"DTEND;TZID={tz}:{event.dtend.strftime('%Y%m%dT%H%M%S')}")
        lines.append(f"SUMMARY:{event.summary}")
        if event.colour:
            lines.append(f"COLOR:{event.colour[len('COLOR_'):].lower()}")
        if event.description:
            escaped = event.description.replace("\n", "\\n")
            lines.append(f"DESCRIPTION:{escaped}")
        lines.append("END:VEVENT")
    lines.append("END:VCALENDAR")

    with open(filepath, "w") as f:
        f.write("\n".join(lines) + "\n")
