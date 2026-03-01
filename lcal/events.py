from datetime import date as date_type
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


class Event:
    def __init__(self, summary, dtstart, dtend=None, timezone=None,
                 colour=None, description=None):
        self.summary = summary
        self.dtstart = dtstart
        self.dtend = dtend
        self.timezone = timezone
        self.colour = colour
        self.description = description

    def is_all_day(self):
        # Return True if this is an all-day event
        return type(self.dtstart) is date_type

    def to_tz(self, dt, tz_str):
        # Avoid checking tz for empty string or all day event
        if dt is None or type(dt) is date_type:
            return dt
        # Convert dt to the given IANA tz
        try:
            target = ZoneInfo(tz_str)
            if dt.tzinfo is None:
                src = ZoneInfo(self.timezone)
                dt = dt.replace(tzinfo=src)
            return dt.astimezone(target)
        except (ZoneInfoNotFoundError, KeyError):
            return dt

    def date_in_tz(self, tz_str):
        # Return the calendar date of the event in tz
        # Return stored date for all-day events
        if self.is_all_day():
            return self.dtstart
        return self.to_tz(self.dtstart, tz_str).date()

    def time_str_in_tz(self, tz_str, time_24h=True):
        # Return the formatted time range string converted to tz
        if self.is_all_day():
            return "All day"

        fmt = "%H:%M" if time_24h else "%I:%M%p"

        # Get formatted start time converted to tz
        start = self.to_tz(self.dtstart, tz_str).strftime(fmt)

        # Get the formatted time range if there is end time
        if self.dtend:
            end = self.to_tz(self.dtend, tz_str).strftime(fmt)
            if time_24h:
                return f"{start} -> {end}"
            else:
                return f"{start}->{end}"

        return start

    def date(self):
        # Return the date of the event in the event's own stored timezone
        if self.is_all_day():
            return self.dtstart
        return self.date_in_tz(self.timezone)
