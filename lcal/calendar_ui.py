import calendar
import curses
import os
import subprocess
import tempfile
from collections import defaultdict
from datetime import date, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from lcal.colours import EVENT_COLOUR_PAIRS, init_colours
from lcal.config import load_config, save_config, DEFAULT_CONFIG, TODO_DIR
from lcal.events import Event
from lcal.ics_parser import parse_ics, write_ics
from lcal.todo import add_todo, change_todo_priority, delete_todo, load_todos, rename_todo, set_todo_colour


def _split_words(text, width):
    # Return text as normal if it fits
    if len(text) <= width:
        return text, ""
    if width <= 0:
        return "", text
    # Break words instead of character
    if width < len(text) and text[width] == " ":
        return text[:width], text[width + 1:]
    last_space = text[:width].rfind(" ")
    if last_space > 0:
        return text[:last_space], text[last_space + 1:]
    # Falls back to a hard character break
    return text[:width], text[width:]


def _truncate_words(text, width):
    # Truncates event name to fit in the box and appends (...) for truncated events
    if len(text) <= width:
        return text
    if width <= 1:
        return text[:width]
    chunk = text[:width-3]
    return chunk + "..."


class CalendarApp:
    # Main calendar app with curses tui
    def __init__(self):
        self.config = load_config()
        self.ics_path = self.config.get("ics_path", DEFAULT_CONFIG["ics_path"])
        self.timezone = self.config.get("timezone", DEFAULT_CONFIG["timezone"])
        self.show_timezone = self.config.get(
            "show_timezone", DEFAULT_CONFIG["show_timezone"]
        )
        self.show_day_borders = self.config.get(
            "show_day_borders", DEFAULT_CONFIG["show_day_borders"]
        )
        self.first_weekday = self.config.get(
            "first_weekday", DEFAULT_CONFIG["first_weekday"]
        ) - 1
        self.show_events_tab = self.config.get(
            "show_events_tab", DEFAULT_CONFIG["show_events_tab"]
        )
        self.holidays_ics_path = self.config.get(
            "holidays_ics_path", DEFAULT_CONFIG["holidays_ics_path"]
        )
        self.holiday_colour = self.config.get(
            "holiday_colour", DEFAULT_CONFIG["holiday_colour"]
        )
        self.day_names = self.config.get(
            "day_names", DEFAULT_CONFIG["day_names"]
        )
        self.month_names = self.config.get(
            "month_names", DEFAULT_CONFIG["month_names"]
        )
        self.time_24h = self.config.get(
            "time_24h", DEFAULT_CONFIG["time_24h"]
        )
        self.date_format = self.config.get(
            "date_format", DEFAULT_CONFIG["date_format"]
        )
        self.event_date_format = self.config.get(
            "event_date_format", DEFAULT_CONFIG["event_date_format"]
        )
        self.keybindings = {
            **DEFAULT_CONFIG["keybindings"],
            **self.config.get("keybindings", {}),
        }
        self.events = []
        self.holidays = []
        self.today = date.today()
        self.current_year = self.today.year
        self.current_month = self.today.month
        self.cursor_row = 0
        self.cursor_col = 0
        self.load_events()
        self.load_holidays()
        # Start with cursor on today
        self._go_today(self.get_month_grid())
        self.event_cursor = 0
        self.event_selection_mode = False
        self.sidebar_ratio = self.config.get(
            "sidebar_ratio", DEFAULT_CONFIG["sidebar_ratio"]
        )
        self.sidebar_focused = False
        self.todo_cursor = 0
        self.notes_extension = self.config.get(
            "notes_extension", DEFAULT_CONFIG["notes_extension"]
        )
        self.todos = load_todos(self.notes_extension)
        self.editor = self.config.get("editor", DEFAULT_CONFIG["editor"])
        self.event_spacing = self.config.get("event_spacing", DEFAULT_CONFIG["event_spacing"])
        self.events_tab_ratio = self.config.get("events_tab_ratio", DEFAULT_CONFIG["events_tab_ratio"])

    def load_events(self):
        # Load events from the ICS file
        try:
            self.events = parse_ics(self.ics_path)
        except FileNotFoundError:
            self.events = []

    def load_holidays(self):
        # Load holidays from the holidays ICS file and apply the holiday colour
        if not self.holidays_ics_path:
            self.holidays = []
            return
        try:
            holidays = parse_ics(self.holidays_ics_path)
            for h in holidays:
                h.colour = self.holiday_colour
            self.holidays = holidays
        except FileNotFoundError:
            self.holidays = []

    def get_holidays_by_date(self):
        # Return a dictionary mapping date to a list of holiday events
        by_date = defaultdict(list)
        for holiday in self.holidays:
            by_date[holiday.date()].append(holiday)
        return by_date

    def get_events_by_date(self):
        # Return a dictionary mapping date to a list of events sorted by start time
        by_date = defaultdict(list)
        for event in self.events:
            by_date[event.date_in_tz(self.timezone)].append(event)
        for day_events in by_date.values():
            day_events.sort(key=lambda e: (
                (0,) if e.is_all_day() else (1, e.to_tz(e.dtstart, self.timezone))
            ))
        return by_date

    def get_month_grid(self):
        # Return a grid of dates for the current month
        cal = calendar.Calendar(firstweekday=self.first_weekday)
        month_days = cal.monthdayscalendar(self.current_year, self.current_month)
        grid = []
        for week in month_days:
            row = []
            for day in week:
                if day == 0:
                    row.append(None)
                else:
                    row.append(date(self.current_year, self.current_month, day))
            grid.append(row)
        return grid

    def _get_full_grid(self):
        # Return a complete grid with actual dates for all cells including prev/next month
        cal = calendar.Calendar(firstweekday=self.first_weekday)
        return cal.monthdatescalendar(self.current_year, self.current_month)

    def run(self, stdscr):
        # Main application loop
        curses.curs_set(0)
        curses.use_default_colors()

        # Initialise color pairs
        if curses.has_colors():
            init_colours(self.config)

        while True:
            stdscr.clear()
            height, width = stdscr.getmaxyx()

            # Compute elements width
            sidebar_w = max(20, int(width * self.sidebar_ratio))
            cal_width = width - sidebar_w

            grid = self.get_month_grid()
            full_grid = self._get_full_grid()
            events_by_date = self.get_events_by_date()
            holidays_by_date = self.get_holidays_by_date()

            # Clamp cursor position
            num_weeks = len(grid)
            self.cursor_row = max(0, min(self.cursor_row, num_weeks - 1))
            self.cursor_col = max(0, min(self.cursor_col, 6))

            # Clamp event cursor and validate event selection mode
            if self.event_selection_mode:
                _cur_day = grid[self.cursor_row][self.cursor_col]
                if _cur_day is None:
                    self.event_selection_mode = False
                else:
                    _day_evts = events_by_date.get(_cur_day, [])
                    if not _day_evts:
                        self.event_selection_mode = False
                    else:
                        self.event_cursor = max(
                            0, min(self.event_cursor, len(_day_evts) - 1)
                        )

            # Compute cell width
            cell_width = max(4, (cal_width - 2) // 7)

            # Snap cal_width to eliminate the gap between cal and sidebar
            actual_cal_width = 2 + 7 * cell_width
            if actual_cal_width < cal_width:
                cal_width = actual_cal_width
                sidebar_w = width - cal_width

            # Write header
            month_name = self.month_names[self.current_month - 1]
            header = f" {month_name} {self.current_year} "
            header_row = 1
            stdscr.addstr(header_row, max(0, (cal_width - len(header)) // 2), header,
                          curses.A_BOLD | curses.color_pair(2))

            # Display timezone in the top-right corner of the calendar area.
            tz_label = self.timezone.split("/")[-1] if "/" in self.timezone else self.timezone
            tz_label = f"Timezone: {tz_label}"
            tz_x = cal_width - len(tz_label) - 3
            if self.show_timezone and tz_x > 0 and header_row < height - 1:
                try:
                    stdscr.addstr(header_row, tz_x, tz_label)
                except curses.error:
                    pass

            # Write day-of-week headers
            all_day_names = self.day_names
            day_names = [all_day_names[(self.first_weekday + i) % 7]
                         for i in range(7)]
            header_y = 3
            for col, name in enumerate(day_names):
                x = 1 + col * cell_width
                if x + len(name) < cal_width:
                    attr = curses.A_BOLD
                    # Highlight Sunday
                    col_weekday = (self.first_weekday + col) % 7
                    if col_weekday == 6:  # Sunday
                        attr |= curses.color_pair(3)
                    stdscr.addstr(header_y, x, name.center(cell_width), attr)

            # Distribute the available terminal rows evenly across all weeks
            start_y = 5
            available = height - start_y - 1
            row_tops = [start_y + (available * i) // num_weeks
                        for i in range(num_weeks + 1)]

            # Helper function to build a horizontal border line
            def _sep_line(left_char, mid_char, right_char):
                sw = min(cal_width, 1 + 7 * cell_width)
                sc = ["─"] * sw
                sc[0] = left_char
                for c in range(6):  # internal column-border positions
                    bx = (c + 1) * cell_width
                    if 0 < bx < sw:
                        sc[bx] = mid_char
                bx = 7 * cell_width  # right outer edge
                if 0 < bx < sw:
                    sc[bx] = right_char
                return "".join(sc)

            # Accent colour for whichever section currently has focus.
            cal_border_attr = (
                curses.color_pair(14) if not self.sidebar_focused
                else curses.A_NORMAL
            )

            # Draw outer enclosing box top at row 0
            if 0 < height - 1:
                try:
                    stdscr.addstr(0, 0, _sep_line("┌", "─", "┐"),
                                  cal_border_attr)
                except curses.error:
                    pass

            # Draw separator between day names and the grid and between year and day names
            top_y = start_y - 1
            if top_y < height - 1:
                try:
                    sep_mid = "┼" if self.show_day_borders else "─"
                    stdscr.addstr(top_y, 0, _sep_line("├", sep_mid, "┤"),
                                  cal_border_attr)
                    sep_mid = "┬" if self.show_day_borders else "─"
                    stdscr.addstr(top_y - 2, 0, _sep_line("├", sep_mid, "┤"),
                                  cal_border_attr)
                except curses.error:
                    pass

            # Draw left and right border columns for header rows and content rows
            right_col = 7 * cell_width
            sep_rows = (
                {row_tops[i + 1] - 1 for i in range(num_weeks - 1)}
                if self.show_day_borders else set()
            )
            for ey in list(range(1, start_y - 1, 2)) + list(range(start_y, row_tops[num_weeks] - 1)):
                if ey >= height - 1:
                    break
                try:
                    stdscr.addstr(ey, 0, "│", cal_border_attr)
                except curses.error:
                    pass
                border_char = "┤" if ey in sep_rows else "│"
                try:
                    stdscr.addstr(ey, right_col, border_char, cal_border_attr)
                except curses.error:
                    pass

            # Draw grid
            for row_idx, week in enumerate(grid):
                cell_height = max(3, row_tops[row_idx + 1] - row_tops[row_idx])
                for col_idx, day_date in enumerate(week):
                    y = row_tops[row_idx]

                    if y >= height - 1:
                        continue

                    is_cursor = (row_idx == self.cursor_row
                                 and col_idx == self.cursor_col
                                 and not self.sidebar_focused)
                    is_today = (day_date == self.today)
                    is_last_col = (col_idx == 6)
                    is_last_row = (row_idx == num_weeks - 1)

                    overflow_date = (full_grid[row_idx][col_idx]
                                     if day_date is None else None)
                    x = 1 + col_idx * cell_width
                    selected_event_idx = (
                        self.event_cursor
                        if self.event_selection_mode and is_cursor
                        else None
                    )
                    self._draw_cell(stdscr, y, x, cell_width, cell_height,
                                    day_date, events_by_date, is_cursor,
                                    is_today, cal_width, height,
                                    self.show_day_borders, is_last_col,
                                    is_last_row, overflow_date,
                                    selected_event_idx, cal_border_attr,
                                    holidays_by_date)

                # Draw horizontal separator between rows
                if self.show_day_borders and row_idx < num_weeks - 1:
                    sep_y = row_tops[row_idx + 1] - 1
                    if sep_y < height - 1:
                        try:
                            stdscr.addstr(sep_y, 0, _sep_line("├", "┼", "┤"),
                                          cal_border_attr)
                        except curses.error:
                            pass

            # Draw bottom border that closes the last row
            bottom_y = row_tops[num_weeks] - 1
            bottom_mid = "┴" if self.show_day_borders else "─"
            try:
                stdscr.addstr(bottom_y, 0, _sep_line("└", bottom_mid, "┘"),
                              cal_border_attr)
            except curses.error:
                pass

            # Draw sidebar
            cur_date = full_grid[self.cursor_row][self.cursor_col]
            self._draw_sidebar(stdscr, cal_width, sidebar_w, height, cur_date, events_by_date, holidays_by_date)

            stdscr.refresh()

            # Handle input
            key = stdscr.getch()

            # Tab toggles focus between calendar and sidebar
            if key == 9:  # Tab key
                if self.event_selection_mode:
                    self.event_selection_mode = False
                self.sidebar_focused = not self.sidebar_focused
                continue

            if key == self._kb("quit"):
                break
            elif key == self._kb("goto_date"):
                self._goto_date(stdscr, height, width)
            elif key == self._kb("change_timezone"):
                self._change_timezone(stdscr, height, width)

            if self.sidebar_focused:
                if key == self._kb("move_down") or key == curses.KEY_DOWN:
                    if self.todos:
                        self.todo_cursor = min(self.todo_cursor + 1, len(self.todos) - 1)
                elif key == self._kb("move_up") or key == curses.KEY_UP:
                    if self.todos:
                        self.todo_cursor = max(self.todo_cursor - 1, 0)
                elif key == self._kb("todo_add"):
                    self._add_todo(stdscr, height, width)
                elif key == self._kb("todo_edit"):
                    self._edit_todo(stdscr, height, width)
                elif key == self._kb("todo_open"):
                    self._open_todo(stdscr)
                elif key == self._kb("todo_delete"):
                    self._delete_todo(stdscr)
                elif key == self._kb("todo_priority_up"):
                    self._change_todo_priority(stdscr, 1)
                elif key == self._kb("todo_priority_down"):
                    self._change_todo_priority(stdscr, -1)
            else:
                if key == self._kb("move_left") or key == curses.KEY_LEFT:
                    self._move_cursor(grid, 0, -1)
                    self.event_cursor = 0
                elif key == self._kb("move_right") or key == curses.KEY_RIGHT:
                    self._move_cursor(grid, 0, 1)
                    self.event_cursor = 0
                elif key == self._kb("add_event"):
                    self._add_event(stdscr, grid, height, width)
                elif key == self._kb("go_today"):
                    self._go_today(grid)

                if self.event_selection_mode:
                    if key == 27:  # Escape key
                        self.event_selection_mode = False
                    elif key == self._kb("move_down") or key == curses.KEY_DOWN:
                        self._move_event_cursor(events_by_date, 1)
                    elif key == self._kb("move_up") or key == curses.KEY_UP:
                        self._move_event_cursor(events_by_date, -1)
                    elif key == self._kb("edit_description"):
                        self._edit_description(stdscr, grid, events_by_date)
                    elif key == self._kb("edit_event"):
                        self._edit_event(stdscr, grid, events_by_date, height, width)
                    elif key == self._kb("delete_event"):
                        self._delete_event(stdscr, grid, events_by_date, height, width)
                else:
                    if key == self._kb("move_down") or key == curses.KEY_DOWN:
                        self._move_cursor(grid, 1, 0)
                    elif key == self._kb("move_up") or key == curses.KEY_UP:
                        self._move_cursor(grid, -1, 0)
                    elif key == self._kb("next_month"):
                        self._next_month()
                    elif key == self._kb("prev_month"):
                        self._prev_month()
                    elif key == self._kb("enter_event_selection"):
                        self._enter_event_selection(grid, events_by_date)

    def _draw_sidebar(self, stdscr, x_start, sidebar_w, height, selected_date=None, events_by_date=None, holidays_by_date=None):
        # Draw the todo list and events sidebar
        if sidebar_w < 4:
            return

        cw = sidebar_w - 3 # usable content width
        wrap_w = max(1, cw - 1) # wrapping width
        content_x = x_start + 2 # x of inner content
        right_x = x_start + sidebar_w - 1 # x of right border char
        mid = max(1, int((height - 1) * (1 - self.events_tab_ratio)))  # row where EVENTS box starts

        accent_attr = curses.color_pair(14)

        # Helper function to draw a horizontal line
        def _hline(y, lc, fill, rc, attr):
            if y < 0 or y >= height - 1:
                return
            line = lc + fill * (sidebar_w - 2) + rc
            try:
                stdscr.addstr(y, x_start, line[:sidebar_w], attr)
            except curses.error:
                pass

        # Helper function to draw vertical line
        def _vsides(y_start, y_end, attr):
            for row in range(y_start, y_end):
                if row >= height - 1:
                    break
                try:
                    stdscr.addstr(row, x_start, "│", attr)
                except curses.error:
                    pass
                try:
                    stdscr.addstr(row, right_x, "│", attr)
                except curses.error:
                    pass

        # TODO box
        # When events tab is hidden, TODO takes the full sidebar height.
        todo_attr = accent_attr if self.sidebar_focused else curses.A_NORMAL
        bot_y = height - 2
        if self.show_events_tab:
            todo_bot = mid - 1
        else:
            todo_bot = bot_y
        _hline(0, "┌", "─", "┐", todo_attr)
        _vsides(1, todo_bot, todo_attr)
        _hline(todo_bot, "└", "─", "┘", todo_attr)

        # TODO title
        title = " TODO "
        title_attr = curses.A_BOLD | (todo_attr if self.sidebar_focused else curses.A_NORMAL)
        try:
            stdscr.addstr(1, content_x, title[:cw], title_attr)
        except curses.error:
            pass

        # Underline below TODO title
        try:
            if 2 < todo_bot:
                stdscr.addstr(2, x_start, "├" + "─" * (sidebar_w - 2) + "┤", todo_attr)
        except curses.error:
            pass

        # TODO items
        row = 3
        for idx, item in enumerate(self.todos):
            if row >= todo_bot:
                break
            is_selected = self.sidebar_focused and idx == self.todo_cursor
            attr = curses.A_REVERSE if is_selected else curses.A_NORMAL
            if curses.has_colors() and item.colour:
                pair_num = EVENT_COLOUR_PAIRS.get(item.colour)
                if pair_num is not None:
                    attr |= curses.color_pair(pair_num)
            has_content = os.path.getsize(item.filepath) > 0 if os.path.exists(item.filepath) else False
            sep = ">" if has_content else "."
            label = f"{item.priority}{sep} {item.name}"
            indent = " " * len(f"{item.priority}{sep} ")
            remaining = label
            first_line = True
            while remaining and row < todo_bot:
                if first_line:
                    chunk, remaining = _split_words(remaining, wrap_w)
                    first_line = False
                else:
                    inner = max(1, wrap_w - len(indent))
                    piece, remaining = _split_words(remaining, inner)
                    chunk = indent + piece
                try:
                    stdscr.addstr(row, content_x, chunk.ljust(cw), attr)
                except curses.error:
                    pass
                row += 1

        if not self.show_events_tab:
            return

        # EVENTS box
        events_attr = accent_attr if self.event_selection_mode else curses.A_NORMAL
        _hline(mid, "┌", "─", "┐", events_attr)
        _vsides(mid + 1, bot_y, events_attr)
        _hline(bot_y, "└", "─", "┘", events_attr)

        # When sidebar is focused and todos exist, show selected todo content
        preview_todo = self.sidebar_focused and bool(self.todos)
        selected_todo = self.todos[self.todo_cursor] if preview_todo else None

        # Events/Todo preview title
        if preview_todo:
            ev_title = f" {selected_todo.name} "
        else:
            ev_title = " Events "
        ev_title_attr = curses.A_BOLD
        try:
            stdscr.addstr(mid + 1, content_x, ev_title[:cw], ev_title_attr)
        except curses.error:
            pass

        # Underline below title
        try:
            if mid + 2 < bot_y:
                stdscr.addstr(mid + 2, x_start, "├" + "─" * (sidebar_w - 2) + "┤", events_attr)
        except curses.error:
            pass

        ev_row = mid + 3

        if preview_todo:
            # Show the selected todo item's file content
            todo_content = ""
            fpath = os.path.realpath(selected_todo.filepath)
            if os.path.exists(fpath):
                try:
                    with open(fpath, "r") as f:
                        todo_content = f.read()
                except OSError:
                    todo_content = ""
            for line in todo_content.splitlines():
                if ev_row >= bot_y:
                    break
                if not line:
                    # Blank line – advance the row
                    ev_row += 1
                    continue
                remaining = line
                while remaining and ev_row < bot_y:
                    chunk, remaining = _split_words(remaining, wrap_w)
                    try:
                        stdscr.addstr(ev_row, content_x, chunk.ljust(cw), curses.A_NORMAL)
                    except curses.error:
                        pass
                    ev_row += 1
        else:
            # Events content: holidays first, then regular events
            day_holidays = []
            day_events = []
            if selected_date is not None:
                if holidays_by_date is not None:
                    day_holidays = holidays_by_date.get(selected_date, [])
                if events_by_date is not None:
                    day_events = events_by_date.get(selected_date, [])
            all_day_events = day_holidays + day_events
            if selected_date is not None:
                date_label = selected_date.strftime(self.event_date_format)
                try:
                    if ev_row < bot_y:
                        stdscr.addstr(ev_row, content_x, date_label[:cw], curses.A_BOLD)
                        ev_row += 2
                except curses.error:
                    pass

            # Loop over all events
            for event_index, event in enumerate(all_day_events):
                is_holiday = (event_index < len(day_holidays))
                if ev_row >= bot_y:
                    break
                # Determine event colour attribute
                evt_attr = curses.A_NORMAL
                if curses.has_colors() and event.colour:
                    pair_num = EVENT_COLOUR_PAIRS.get(event.colour)
                    if pair_num is not None:
                        evt_attr = curses.color_pair(pair_num)
                # Time string on its own line (not shown for holidays)
                if not is_holiday:
                    if ev_row < bot_y:
                        try:
                            stdscr.addstr(ev_row, content_x, event.time_str_in_tz(self.timezone, self.time_24h)[:wrap_w].ljust(cw), evt_attr)
                        except curses.error:
                            pass
                        ev_row += 1
                # Event name: wrap across multiple lines with consistent indent
                prefix = "" if is_holiday else ("> " if event.description else "  ")
                indent = " " * len(prefix)
                full_name = prefix + event.summary
                remaining = full_name
                first_line = True
                while remaining and ev_row < bot_y:
                    if first_line:
                        chunk, remaining = _split_words(remaining, wrap_w)
                        first_line = False
                    else:
                        inner = max(1, wrap_w - len(indent))
                        piece, remaining = _split_words(remaining, inner)
                        chunk = indent + piece
                    try:
                        stdscr.addstr(ev_row, content_x, chunk.ljust(cw), evt_attr)
                    except curses.error:
                        pass
                    ev_row += 1
                ev_row += 1  # spacing between events

    def _add_todo(self, stdscr, height, width):
        # Prompt user for name and priority, then create a todo item
        prompt_y = height - 1

        name = self._prompt(stdscr, "Todo name: ", prompt_y, width)
        if name is None or not name:
            return

        try:
            stdscr.addstr(
                prompt_y, 0, "Priority (1-9): "[:width - 1].ljust(width - 1),
                curses.A_BOLD,
            )
        except curses.error:
            pass
        stdscr.refresh()
        pri_ch = stdscr.getch()
        if pri_ch in (curses.KEY_ENTER, ord("\n"), ord("\r")):
            priority = 1
        elif pri_ch < ord("1") or pri_ch > ord("9"):
            try:
                stdscr.addstr(
                    prompt_y, 0,
                    "Invalid priority: enter a digit from 1 to 9"[:width - 1].ljust(width - 1),
                    curses.A_BOLD,
                )
                stdscr.refresh()
                stdscr.getch()
            except curses.error:
                pass
            return
        else:
            priority = pri_ch - ord("0")

        # Get todo colour (optional)
        escaped, colour = self._prompt_colour(stdscr, prompt_y, width)
        if escaped:
            return

        add_todo(name, priority, colour, self.notes_extension)
        self.todos = load_todos(self.notes_extension)
        self.todo_cursor = min(self.todo_cursor, max(0, len(self.todos) - 1))

    def _open_todo(self, stdscr):
        # Open the selected todo's markdown file in an editor
        if not self.todos:
            return
        item = self.todos[self.todo_cursor]
        curses.endwin()
        editor = self.editor or DEFAULT_CONFIG['editor']
        subprocess.call([editor, item.filepath])
        stdscr.refresh()

    def _delete_todo(self, stdscr):
        # Delete the currently selected todo item
        if not self.todos:
            return
        height, width = stdscr.getmaxyx()
        item = self.todos[self.todo_cursor]
        confirmed = self._prompt_yn(
            stdscr,
            f"Delete '{item.name}'? (y/N): ",
            height - 1, width,
        )
        if not confirmed:
            return
        delete_todo(item)
        self.todos = load_todos(self.notes_extension)
        self.todo_cursor = min(self.todo_cursor, max(0, len(self.todos) - 1))

    def _change_todo_priority(self, stdscr, delta):
        # Increment or decrement the selected todo's priority
        if not self.todos:
            return
        item = self.todos[self.todo_cursor]
        new_priority = item.priority + delta
        if new_priority < 1 or new_priority > 9:
            return
        change_todo_priority(item, new_priority)
        self.todos = load_todos(self.notes_extension)
        # Keep the cursor on the same item after sorting
        for i, t in enumerate(self.todos):
            if t.filepath == item.filepath:
                self.todo_cursor = i
                break
        else:
            self.todo_cursor = min(self.todo_cursor, max(0, len(self.todos) - 1))

    def _edit_todo(self, stdscr, height, width):
        # Edit an attribute of the currently selected todo item.
        if not self.todos:
            return
        item = self.todos[self.todo_cursor]
        prompt_y = height - 1

        attr_prompt = "Edit (p=priority n=todo name c=colour): "
        try:
            stdscr.addstr(
                prompt_y, 0, attr_prompt[:width - 1].ljust(width - 1),
                curses.A_BOLD,
            )
        except curses.error:
            pass
        stdscr.refresh()
        ch = stdscr.getch()

        if ch == ord("p"):
            try:
                stdscr.addstr(
                    prompt_y, 0, "Priority (1-9): "[:width - 1].ljust(width - 1),
                    curses.A_BOLD,
                )
            except curses.error:
                pass
            stdscr.refresh()
            pri_ch = stdscr.getch()
            if pri_ch in (curses.KEY_ENTER, ord("\n"), ord("\r")):
                new_priority = 1
            elif ord("1") <= pri_ch <= ord("9"):
                new_priority = pri_ch - ord("0")
            else:
                new_priority = None
            if new_priority is None:
                try:
                    stdscr.addstr(
                        prompt_y, 0,
                        "Invalid priority: enter a digit from 1 to 9"[:width - 1].ljust(width - 1),
                        curses.A_BOLD,
                    )
                    stdscr.refresh()
                    stdscr.getch()
                except curses.error:
                    pass
            else:
                change_todo_priority(item, new_priority)
                self.todos = load_todos(self.notes_extension)
                for i, t in enumerate(self.todos):
                    if t.filepath == item.filepath:
                        self.todo_cursor = i
                        break
                else:
                    self.todo_cursor = min(self.todo_cursor, max(0, len(self.todos) - 1))

        elif ch == ord("n"):
            name = self._prompt(stdscr, "Todo name: ", prompt_y, width,
                                prefill=item.name or "")
            if name is not None and name:
                rename_todo(item, name)
                self.todos = load_todos(self.notes_extension)
                # Keep the cursor on the same item after renaming
                for i, t in enumerate(self.todos):
                    if t.filepath == item.filepath:
                        self.todo_cursor = i
                        break
                else:
                    self.todo_cursor = min(self.todo_cursor, max(0, len(self.todos) - 1))

        elif ch == ord("c"):
            escaped, colour = self._prompt_colour(stdscr, prompt_y, width)
            if not escaped:
                set_todo_colour(item, colour)
                self.todos = load_todos(self.notes_extension)
                # Keep the cursor on the same item after changing colour
                for i, t in enumerate(self.todos):
                    if t.filepath == item.filepath:
                        self.todo_cursor = i
                        break
                else:
                    self.todo_cursor = min(self.todo_cursor, max(0, len(self.todos) - 1))

    def _draw_cell(self, stdscr, y, x, cell_width, cell_height,
                   day_date, events_by_date, is_cursor, is_today,
                   max_width, max_height, show_borders=False,
                   is_last_col=True, is_last_row=True, overflow_date=None,
                   selected_event_idx=None, border_attr=0, holidays_by_date=None):
        # Draw a single calendar cell
        cw_border = (cell_width - 1) if show_borders else cell_width
        # Leave last row of cell for horizontal separator
        content_height = (cell_height - 1) if show_borders else cell_height

        if day_date is None:
            # Other-month dates (dim)
            overflow_attr = curses.A_DIM
            for row in range(cell_height):
                ey = y + row
                if ey >= max_height - 1 or x >= max_width:
                    break
                cw = min(cw_border, max_width - x)
                if cw <= 0:
                    break
                try:
                    if row == 0 and overflow_date is not None:
                        day_str = str(overflow_date.day)
                        stdscr.addstr(ey, x, day_str, overflow_attr)
                        pad = cw - len(day_str)
                        if pad > 0:
                            stdscr.addstr(ey, x + len(day_str), " " * pad)
                    else:
                        stdscr.addstr(ey, x, " " * cw)
                except curses.error:
                    pass
        else:
            # Determine day number attribute
            is_weekend = day_date.weekday() == 6  # Sunday colour
            day_holidays = (holidays_by_date.get(day_date, [])
                            if holidays_by_date is not None else [])
            # Cursor: square brackets around the date number
            bracket_attr = curses.color_pair(1) | curses.A_BOLD
            if is_today:
                day_attr = curses.color_pair(4) | curses.A_BOLD
            elif is_weekend:
                day_attr = curses.color_pair(3) | curses.A_BOLD
            else:
                day_attr = curses.A_NORMAL

            # Apply holiday colour to the date number for days that have holidays
            if not is_today and day_holidays and curses.has_colors():
                hol_pair = EVENT_COLOUR_PAIRS.get(self.holiday_colour)
                if hol_pair is not None:
                    day_attr = curses.color_pair(hol_pair) | curses.A_BOLD

            attr = curses.A_NORMAL

            # Draw day number
            day_str = str(day_date.day)
            cw = min(cw_border, max_width - x)
            if cw <= 0:
                return

            try:
                if is_cursor:
                    # Draw [day] with square brackets
                    stdscr.addstr(y, x, "[", bracket_attr)
                    if x + 1 < max_width:
                        stdscr.addstr(y, x + 1, day_str, day_attr)
                    close_x = x + 1 + len(day_str)
                    if close_x < max_width:
                        stdscr.addstr(y, close_x, "]", bracket_attr)
                    used = 1 + len(day_str) + 1  # "[" + day_str + "]"
                    pad = cw - used
                    if pad > 0:
                        stdscr.addstr(y, x + used, " " * pad, attr)
                else:
                    # Draw day number with its own attribute, then pad with cell attr
                    stdscr.addstr(y, x, day_str, day_attr)
                    pad = cw - len(day_str)
                    if pad > 0:
                        stdscr.addstr(y, x + len(day_str), " " * pad, attr)
            except curses.error:
                pass

            # Draw events
            # Holidays (read-only) are shown first, then regular events
            day_events = day_holidays + events_by_date.get(day_date, [])

            # Compute scroll offset so the selected event is always visible
            lines_per_event = 3 if self.event_spacing else 2
            max_visible_events = max(0, (content_height - 1) // lines_per_event)
            if selected_event_idx is not None and max_visible_events > 0:
                scroll_offset = max(0, selected_event_idx - max_visible_events + 1)
            else:
                scroll_offset = 0

            event_lines = 0
            for render_idx, event in enumerate(day_events[scroll_offset:]):
                event_idx = render_idx + scroll_offset
                is_holiday = (event_idx < len(day_holidays))
                evt_attr = (
                    curses.A_REVERSE
                    if event_idx == selected_event_idx
                    else curses.A_NORMAL
                )
                if curses.has_colors() and event.colour:
                    pair_num = EVENT_COLOUR_PAIRS.get(event.colour)
                    if pair_num is not None:
                        evt_attr |= curses.color_pair(pair_num)
                # Blank spacer line between the date number and the first event
                if self.event_spacing:
                    ey = y + 1 + event_lines
                    if ey >= y + content_height or ey >= max_height - 1:
                        break
                    try:
                        stdscr.addstr(ey, x, " " * cw)
                    except curses.error:
                        pass
                    event_lines += 1

                if not is_holiday:
                    # Time string
                    ey = y + 1 + event_lines
                    if ey >= y + content_height or ey >= max_height - 1:
                        break
                    time_str = event.time_str_in_tz(self.timezone, self.time_24h)
                    try:
                        stdscr.addstr(ey, x, time_str[:cw].ljust(cw), evt_attr)
                    except curses.error:
                        pass
                    event_lines += 1

                # Event name (no prefix/indent for holidays)
                ey = y + 1 + event_lines
                if ey >= y + content_height or ey >= max_height - 1:
                    break
                prefix = "" if is_holiday else ("> " if event.description else "  ")
                indent = " " * len(prefix)
                full_name = prefix + event.summary
                if event_idx == selected_event_idx or is_holiday:
                    # Wrap across multiple lines for holidays and selected event
                    remaining = full_name
                    first_line = True
                    while remaining:
                        ey = y + 1 + event_lines
                        if ey >= y + content_height or ey >= max_height - 1:
                            break
                        if first_line:
                            chunk, remaining = _split_words(remaining, cw)
                            first_line = False
                        else:
                            inner = max(1, cw - len(indent))
                            piece, remaining = _split_words(remaining, inner)
                            chunk = indent + piece
                        try:
                            stdscr.addstr(ey, x, chunk.ljust(cw), evt_attr)
                        except curses.error:
                            pass
                        event_lines += 1
                else:
                    name_str = _truncate_words(full_name, cw)
                    try:
                        stdscr.addstr(ey, x, name_str.ljust(cw), evt_attr)
                    except curses.error:
                        pass
                    event_lines += 1

            # Fill remaining content lines in cell
            for row in range(1 + event_lines, content_height):
                ey = y + row
                if ey >= max_height - 1:
                    break
                try:
                    stdscr.addstr(ey, x, " " * cw)
                except curses.error:
                    pass

        # Draw vertical separator on the right edge of the cell
        if show_borders:
            bx = x + cell_width - 1
            if bx < max_width:
                if day_date is not None:
                    try:
                        stdscr.addstr(3, bx, "│", border_attr)
                    except curses.error:
                        pass
                for row in range(cell_height):
                    ey = y + row
                    if ey >= max_height - 1:
                        break
                    try:
                        stdscr.addstr(ey, bx, "│", border_attr)
                    except curses.error:
                        pass

    def _move_cursor(self, grid, drow, dcol):
        # Move cursor by the given delta, navigating to adjacent month at boundaries
        new_row = self.cursor_row + drow
        new_col = self.cursor_col + dcol
        going_back = drow < 0 or dcol < 0

        if new_col < 0:
            new_col = 6
            new_row -= 1
        elif new_col > 6:
            new_col = 0
            new_row += 1

        num_weeks = len(grid)
        if new_row < 0:
            # Navigate to previous month
            if self.current_month == 1:
                self.current_month = 12
                self.current_year -= 1
            else:
                self.current_month -= 1
            new_grid = self.get_month_grid()
            # Find a valid cell at new_col in the last rows of the previous month
            for row in range(len(new_grid) - 1, -1, -1):
                if new_grid[row][new_col] is not None:
                    self.cursor_row = row
                    self.cursor_col = new_col
                    return
            # Fallback: last valid day of the previous month
            for row in range(len(new_grid) - 1, -1, -1):
                for col in range(6, -1, -1):
                    if new_grid[row][col] is not None:
                        self.cursor_row = row
                        self.cursor_col = col
                        return
        elif new_row >= num_weeks:
            # Navigate to next month
            if self.current_month == 12:
                self.current_month = 1
                self.current_year += 1
            else:
                self.current_month += 1
            new_grid = self.get_month_grid()
            # Find a valid cell at new_col in the first rows of the next month
            for row in range(len(new_grid)):
                if new_grid[row][new_col] is not None:
                    self.cursor_row = row
                    self.cursor_col = new_col
                    return
            # Fallback: first valid day of the next month
            for row in range(len(new_grid)):
                for col in range(7):
                    if new_grid[row][col] is not None:
                        self.cursor_row = row
                        self.cursor_col = col
                        return
        elif grid[new_row][new_col] is not None:
            self.cursor_row = new_row
            self.cursor_col = new_col
        else:
            # Target is a cell from next/prev month
            if going_back:
                # Navigate to previous month
                if self.current_month == 1:
                    self.current_month = 12
                    self.current_year -= 1
                else:
                    self.current_month -= 1
                new_grid = self.get_month_grid()
                for row in range(len(new_grid) - 1, -1, -1):
                    if new_grid[row][new_col] is not None:
                        self.cursor_row = row
                        self.cursor_col = new_col
                        return
                for row in range(len(new_grid) - 1, -1, -1):
                    for col in range(6, -1, -1):
                        if new_grid[row][col] is not None:
                            self.cursor_row = row
                            self.cursor_col = col
                            return
            else:
                # Navigate to next month
                if self.current_month == 12:
                    self.current_month = 1
                    self.current_year += 1
                else:
                    self.current_month += 1
                new_grid = self.get_month_grid()
                for row in range(len(new_grid)):
                    if new_grid[row][new_col] is not None:
                        self.cursor_row = row
                        self.cursor_col = new_col
                        return
                for row in range(len(new_grid)):
                    for col in range(7):
                        if new_grid[row][col] is not None:
                            self.cursor_row = row
                            self.cursor_col = col
                            return

    def _next_month(self):
        # Move to next month of the same grid
        if self.current_month == 12:
            self.current_month = 1
            self.current_year += 1
        else:
            self.current_month += 1
        self._ensure_in_month()

    def _prev_month(self):
        # Move to previous month of the same grid
        if self.current_month == 1:
            self.current_month = 12
            self.current_year -= 1
        else:
            self.current_month -= 1
        self._ensure_in_month()

    def _ensure_in_month(self):
        # Adjust cursor to the prev/next month of the same grid point
        grid = self.get_month_grid()
        self.cursor_row = min(self.cursor_row, len(grid) - 1)
        if grid[self.cursor_row][self.cursor_col] is None:
            if self.cursor_row == 0:
                self.cursor_row = self.cursor_row + 1
            else:
                self.cursor_row = self.cursor_row - 1

    def _go_today(self, grid):
        # Move cursor to today's date
        self.current_year = self.today.year
        self.current_month = self.today.month
        grid = self.get_month_grid()
        for row_idx, week in enumerate(grid):
            for col_idx, day_date in enumerate(week):
                if day_date == self.today:
                    self.cursor_row = row_idx
                    self.cursor_col = col_idx
                    return

    def _kb(self, name):
        # Return the ord() value for the configured keybinding name
        key = self.keybindings.get(name, DEFAULT_CONFIG["keybindings"].get(name, ""))
        if key:
            return ord(key[0])
        return -1

    def _prompt(self, stdscr, prompt_text, y, width, prefill=""):
        # Display a prompt and get text input from the user
        # prefill is an optional string used to pre-populate the input field
        # so the user can edit an existing value rather than typing from scratch
        curses.curs_set(2)
        curses.noecho()
        try:
            stdscr.addstr(y, 0, prompt_text[:width - 1].ljust(width - 1),
                          curses.A_BOLD)
            stdscr.refresh()
            input_str = prefill
            input_x = min(len(prompt_text), width - 2)
            avail = max(1, width - 1 - input_x)  # display columns for input
            cursor_pos = len(input_str)   # position within input_str
            view_offset = 0  # first char of input_str shown at input_x

            def redraw():
                nonlocal view_offset
                # Keep cursor within the visible window
                if cursor_pos - view_offset >= avail:
                    view_offset = cursor_pos - avail + 1
                if cursor_pos < view_offset:
                    view_offset = cursor_pos
                visible = input_str[view_offset:view_offset + avail]
                stdscr.addstr(y, input_x, visible.ljust(avail)[:avail])
                stdscr.move(y, input_x + cursor_pos - view_offset)

            redraw()
            stdscr.refresh()
            while True:
                ch = stdscr.getch()
                if ch == 27:  # Escape
                    return None
                elif ch in (curses.KEY_ENTER, ord("\n"), ord("\r")):
                    break
                elif ch in (curses.KEY_BACKSPACE, 127, 8):
                    if cursor_pos > 0:
                        input_str = (input_str[:cursor_pos - 1]
                                     + input_str[cursor_pos:])
                        cursor_pos -= 1
                        redraw()
                elif ch == curses.KEY_LEFT:
                    if cursor_pos > 0:
                        cursor_pos -= 1
                        redraw()
                elif ch == curses.KEY_RIGHT:
                    if cursor_pos < len(input_str):
                        cursor_pos += 1
                        redraw()
                elif ch == curses.KEY_HOME:
                    cursor_pos = 0
                    redraw()
                elif ch == curses.KEY_END:
                    cursor_pos = len(input_str)
                    redraw()
                elif 32 <= ch <= 0x10FFFF and ch < curses.KEY_MIN:
                    # Printable character
                    input_str = (input_str[:cursor_pos]
                                 + chr(ch)
                                 + input_str[cursor_pos:])
                    cursor_pos += 1
                    redraw()
                stdscr.refresh()
            return input_str.strip()
        except curses.error:
            return ""
        finally:
            curses.curs_set(0)

    def _prompt_yn(self, stdscr, prompt_text, y, width):
        # Display a yes/no prompt and return True for 'y', False otherwise
        try:
            stdscr.addstr(y, 0, prompt_text[:width - 1].ljust(width - 1),
                          curses.A_BOLD)
            stdscr.refresh()
            ch = stdscr.getch()
        except curses.error:
            return False
        return ch in (ord("y"), ord("Y"))

    def _prompt_colour(self, stdscr, y, width):
        # Display a single-key colour selection prompt
        colour_choices = [
            (None, "default"),
            ("COLOR_RED", "red"),
            ("COLOR_GREEN", "green"),
            ("COLOR_YELLOW", "yellow"),
            ("COLOR_BLUE", "blue"),
            ("COLOR_MAGENTA", "magenta"),
            ("COLOR_CYAN", "cyan"),
        ]
        labels = " ".join(
            f"{label[0]}={label}" for _, label in colour_choices
        )
        prompt = f"Colour ({labels}): "
        try:
            stdscr.addstr(y, 0, prompt[:width - 1].ljust(width - 1),
                          curses.A_BOLD)
            stdscr.refresh()
            ch = stdscr.getch()
        except curses.error:
            return False, None
        if ch == 27:  # Escape
            return True, None
        if ch in (curses.KEY_ENTER, ord("\n"), ord("\r")):
            return False, None  # Enter = default
        colour_map = {label[0]: colour_name
                      for colour_name, label in colour_choices}
        key = chr(ch).lower() if 32 <= ch <= 126 else None
        colour = colour_map.get(key)
        if key is not None and key not in colour_map:
            try:
                stdscr.addstr(
                    y, 0,
                    f"Invalid colour: {chr(ch)!r}, choose from d/r/g/y/b/m/c or Enter for default"[:width - 1].ljust(width - 1),
                    curses.A_BOLD,
                )
                stdscr.refresh()
                stdscr.getch()
            except curses.error:
                pass
            return True, None
        return False, colour

    def _parse_time(self, time_str):
        # Parse a time string in HH:MM, HHMM, or 12h format (e.g. 2:30PM)
        if not self.time_24h:
            fmts = ("%H:%M", "%H%M", "%I:%M%p", "%I%M%p")
        else:
            fmts = ("%H:%M", "%H%M")
        for fmt in fmts:
            try:
                return datetime.strptime(time_str.strip(), fmt)
            except ValueError:
                continue
        return None

    def _add_event(self, stdscr, grid, height, width):
        # Add a new event on the selected day
        day_date = grid[self.cursor_row][self.cursor_col]
        if day_date is None:
            return

        prompt_y = height - 1

        # Get start time, enter for all day
        if not self.time_24h:
            start_str = self._prompt(
                stdscr, "Start time (HH:MM, HHMM, HH:MM(am/pm) or HHMM(am/pm), Enter for full-day): ", prompt_y, width
            )
        else:
            start_str = self._prompt(
                stdscr, "Start time (HH:MM or HHMM, Enter for full-day): ", prompt_y, width
            )
        if start_str is None:
            return

        if start_str:
            start_time = self._parse_time(start_str)
            if start_time is None:
                try:
                    stdscr.addstr(
                        prompt_y, 0,
                        "Invalid time format"[:width - 1].ljust(width - 1),
                        curses.A_BOLD,
                    )
                    stdscr.refresh()
                    stdscr.getch()
                except curses.error:
                    pass
                return

            # Get end time, enter to skip
            if not self.time_24h:
                end_str = self._prompt(
                    stdscr, "End time (HH:MM, HHMM, HH:MM(am/pm) or HHMM(am/pm), Enter to skip): ", prompt_y,
                    width
                )
            else:
                end_str = self._prompt(
                    stdscr, "End time (HH:MM or HHMM, Enter to skip): ", prompt_y,
                    width
                )

            if end_str is None:
                return

            # Validate end time before asking for name/colour
            if end_str:
                end_time = self._parse_time(end_str)
                if end_time is None:
                    try:
                        stdscr.addstr(
                            prompt_y, 0,
                            "Invalid time format"[:width - 1].ljust(width - 1),
                            curses.A_BOLD,
                        )
                        stdscr.refresh()
                        stdscr.getch()
                    except curses.error:
                        pass
                    return
                end_dt_check = datetime(
                    day_date.year, day_date.month, day_date.day,
                    end_time.hour, end_time.minute,
                )
                start_dt_check = datetime(
                    day_date.year, day_date.month, day_date.day,
                    start_time.hour, start_time.minute,
                )
                if end_dt_check <= start_dt_check:
                    try:
                        stdscr.addstr(
                            prompt_y, 0,
                            "End time must be after start time"[:width - 1].ljust(width - 1),
                            curses.A_BOLD,
                        )
                        stdscr.refresh()
                        stdscr.getch()
                    except curses.error:
                        pass
                    return
        else:
            start_time = None
            end_str = ""

        # Get event name
        name = self._prompt(stdscr, "Event name: ", prompt_y, width)
        if name is None or not name:
            return

        # Get event colour
        escaped, colour = self._prompt_colour(stdscr, prompt_y, width)
        if escaped:
            return

        if start_time is None:
            # Store dtstart as a date object for all day event
            dtstart = date(day_date.year, day_date.month, day_date.day)
        else:
            dt = datetime(day_date.year, day_date.month, day_date.day,
                          start_time.hour, start_time.minute)
            try:
                dt = dt.replace(tzinfo=ZoneInfo(self.timezone))
            except (ZoneInfoNotFoundError, KeyError):
                pass
            dtstart = dt
        dtend = None
        if end_str:
            end_time = self._parse_time(end_str)
            if end_time is not None:
                dt = datetime(day_date.year, day_date.month, day_date.day,
                              end_time.hour, end_time.minute)
                try:
                    dt = dt.replace(tzinfo=ZoneInfo(self.timezone))
                except (ZoneInfoNotFoundError, KeyError):
                    pass
                dtend = dt

        event = Event(name, dtstart, dtend, self.timezone, colour)
        self.events.append(event)
        write_ics(self.ics_path, self.events)

    def _enter_event_selection(self, grid, events_by_date):
        # Enter event selection mode for the current day's events
        day_date = grid[self.cursor_row][self.cursor_col]
        if day_date is None:
            return
        day_events = events_by_date.get(day_date, [])
        if not day_events:
            return
        self.event_cursor = 0
        self.event_selection_mode = True

    def _move_event_cursor(self, events_by_date, delta):
        # Move the event cursor within the current day's events
        grid = self.get_month_grid()
        day_date = grid[self.cursor_row][self.cursor_col]
        if day_date is None:
            return
        day_events = events_by_date.get(day_date, [])
        if not day_events:
            return
        self.event_cursor = max(0, min(self.event_cursor + delta, len(day_events) - 1))

    def _edit_description(self, stdscr, grid, events_by_date):
        # Open editor to edit the description of the currently selected event
        day_date = grid[self.cursor_row][self.cursor_col]
        if day_date is None:
            return
        day_events = events_by_date.get(day_date, [])
        if not day_events:
            return
        event = day_events[self.event_cursor]

        tmp_fd, tmp_path = tempfile.mkstemp(suffix=f".{self.notes_extension}")
        try:
            with os.fdopen(tmp_fd, "w") as f:
                if event.description:
                    f.write(event.description)
            curses.endwin()
            editor = self.editor or DEFAULT_CONFIG['editor']
            subprocess.call([editor, tmp_path])
            stdscr.refresh()
            with open(tmp_path, "r") as f:
                description = f.read().strip()
            event.description = description if description else None
            write_ics(self.ics_path, self.events)
        finally:
            os.unlink(tmp_path)

    def _edit_event(self, stdscr, grid, events_by_date, height, width):
        # Edit an attribute of the currently selected event
        day_date = grid[self.cursor_row][self.cursor_col]
        if day_date is None:
            return
        day_events = events_by_date.get(day_date, [])
        if not day_events:
            return
        event = day_events[self.event_cursor]

        prompt_y = height - 1
        attr_prompt = "Edit (s=start time e=end time m=move to n=event name c=colour): "
        try:
            stdscr.addstr(
                prompt_y, 0, attr_prompt[:width - 1].ljust(width - 1),
                curses.A_BOLD,
            )
        except curses.error:
            pass
        stdscr.refresh()
        ch = stdscr.getch()

        if ch == ord("n"):
            name = self._prompt(stdscr, "Event name: ", prompt_y, width,
                                prefill=event.summary or "")
            if name is not None and name:
                event.summary = name
                write_ics(self.ics_path, self.events)

        elif ch == ord("s"):
            if not self.time_24h:
                start_str = self._prompt(
                    stdscr,
                    "Start time (HH:MM, HHMM, HH:MM(am/pm) or HHMM(am/pm), Enter for all-day): ",
                    prompt_y, width,
                )
            else:
                start_str = self._prompt(
                    stdscr,
                    "Start time (HH:MM or HHMM, Enter for all-day): ",
                    prompt_y, width,
                )
            if start_str is None:
                return
            ev_date = event.date_in_tz(self.timezone)
            if start_str:
                start_time = self._parse_time(start_str)
                if start_time is None:
                    try:
                        stdscr.addstr(
                            prompt_y, 0,
                            "Invalid time format"[:width - 1].ljust(width - 1),
                            curses.A_BOLD,
                        )
                        stdscr.refresh()
                        stdscr.getch()
                    except curses.error:
                        pass
                    return
                dt = datetime(
                    ev_date.year, ev_date.month, ev_date.day,
                    start_time.hour, start_time.minute,
                )
                try:
                    dt = dt.replace(tzinfo=ZoneInfo(self.timezone))
                except (ZoneInfoNotFoundError, KeyError):
                    pass
                # Check if new start is before end time
                if event.dtend is not None and dt >= event.dtend:
                    try:
                        stdscr.addstr(
                            prompt_y, 0,
                            "Start time must be before end time"[:width - 1].ljust(width - 1),
                            curses.A_BOLD,
                        )
                        stdscr.refresh()
                        stdscr.getch()
                    except curses.error:
                        pass
                    return
                event.dtstart = dt
                event.timezone = self.timezone
                write_ics(self.ics_path, self.events)
            else:
                # Convert to all-day
                event.dtstart = date(ev_date.year, ev_date.month, ev_date.day)
                event.dtend = None
                write_ics(self.ics_path, self.events)

        elif ch == ord("e"):
            if not self.time_24h:
                end_str = self._prompt(
                    stdscr,
                    "End time (HH:MM, HHMM, HH:MM(am/pm) or HHMM(am/pm), Enter to clear): ",
                    prompt_y, width,
                )
            else:
                end_str = self._prompt(
                    stdscr,
                    "End time (HH:MM or HHMM, Enter to clear): ",
                    prompt_y, width,
                )
            if end_str is None:
                return
            if end_str:
                end_time = self._parse_time(end_str)
                if end_time is None:
                    try:
                        stdscr.addstr(
                            prompt_y, 0,
                            "Invalid time format"[:width - 1].ljust(width - 1),
                            curses.A_BOLD,
                        )
                        stdscr.refresh()
                        stdscr.getch()
                    except curses.error:
                        pass
                    return
                ev_date = event.date_in_tz(self.timezone)
                dt = datetime(
                    ev_date.year, ev_date.month, ev_date.day,
                    end_time.hour, end_time.minute,
                )
                try:
                    dt = dt.replace(tzinfo=ZoneInfo(self.timezone))
                except (ZoneInfoNotFoundError, KeyError):
                    pass
                # Check if new end is after start time
                if not event.is_all_day() and event.dtstart is not None and dt <= event.dtstart:
                    try:
                        stdscr.addstr(
                            prompt_y, 0,
                            "End time must be after start time"[:width - 1].ljust(width - 1),
                            curses.A_BOLD,
                        )
                        stdscr.refresh()
                        stdscr.getch()
                    except curses.error:
                        pass
                    return
                event.dtend = dt
            else:
                event.dtend = None
            write_ics(self.ics_path, self.events)

        elif ch == ord("c"):
            escaped, colour = self._prompt_colour(stdscr, prompt_y, width)
            if not escaped:
                event.colour = colour
                write_ics(self.ics_path, self.events)

        elif ch == ord("m"):
            self._move_event(stdscr, event, prompt_y, width)

    def _date_prompt_hint(self):
        # Return the date prompt hint string for the configured date_format
        if self.date_format == "mm/dd/yyyy":
            return "mm/dd or mm/dd/yyyy"
        elif self.date_format == "yyyy-mm-dd":
            return "mm-dd or yyyy-mm-dd"
        elif self.date_format == "yyyy/mm/dd":
            return "mm/dd or yyyy/mm/dd"
        else:
            return "dd/mm or dd/mm/yyyy"

    def _parse_date_str(self, date_str, fallback_date):
        # Parse the date string using the configured date_format
        sep = "-" if self.date_format == "yyyy-mm-dd" else "/"
        parts = date_str.strip().split(sep)
        try:
            if len(parts) == 1:
                day = int(parts[0])
                month, year = fallback_date.month, fallback_date.year
            elif len(parts) == 2:
                if self.date_format in ("mm/dd/yyyy", "yyyy-mm-dd", "yyyy/mm/dd"):
                    month, day = int(parts[0]), int(parts[1])
                else:
                    day, month = int(parts[0]), int(parts[1])
                year = fallback_date.year
            elif len(parts) == 3:
                if self.date_format in ("yyyy-mm-dd", "yyyy/mm/dd"):
                    year, month, day = int(parts[0]), int(parts[1]), int(parts[2])
                elif self.date_format == "mm/dd/yyyy":
                    month, day, year = int(parts[0]), int(parts[1]), int(parts[2])
                else:
                    day, month, year = int(parts[0]), int(parts[1]), int(parts[2])
            else:
                return None
            return date(year, month, day)
        except ValueError:
            return None

    def _move_event(self, stdscr, event, prompt_y, width):
        # Move event to a new date entered by the user
        old_date = event.date_in_tz(self.timezone)
        hint = self._date_prompt_hint()
        date_str = self._prompt(stdscr, f"Move to (dd or {hint}): ", prompt_y, width)
        if date_str is None or not date_str:
            return
        target_date = self._parse_date_str(date_str, old_date)
        if target_date is None:
            try:
                stdscr.addstr(
                    prompt_y, 0,
                    "Invalid date"[:width - 1].ljust(width - 1),
                    curses.A_BOLD,
                )
                stdscr.refresh()
                stdscr.getch()
            except curses.error:
                pass
            return

        if event.is_all_day():
            event.dtstart = target_date
        else:
            event.dtstart = event.dtstart.replace(
                year=target_date.year, 
                month=target_date.month, 
                day=target_date.day
            )
            if event.dtend is not None:
                event.dtend = event.dtend.replace(
                    year=target_date.year, 
                    month=target_date.month, 
                    day=target_date.day
                )
        write_ics(self.ics_path, self.events)

    def _goto_date(self, stdscr, height, width):
        # Navigate to a specific date entered by the user
        prompt_y = height - 1
        hint = self._date_prompt_hint()
        date_str = self._prompt(stdscr, f"Go to (dd or {hint}): ", prompt_y, width)
        if date_str is None or not date_str:
            return
        fallback = date(self.current_year, self.current_month, 1)
        target = self._parse_date_str(date_str, fallback)
        if target is None:
            return
        self.current_year = target.year
        self.current_month = target.month
        grid = self.get_month_grid()
        for row_idx, week in enumerate(grid):
            for col_idx, d in enumerate(week):
                if d == target:
                    self.cursor_row = row_idx
                    self.cursor_col = col_idx
                    return

    def _delete_event(self, stdscr, grid, events_by_date, height, width):
        # Delete the currently selected event on the selected day
        day_date = grid[self.cursor_row][self.cursor_col]
        if day_date is None:
            return

        day_events = events_by_date.get(day_date, [])
        if not day_events:
            return

        idx = self.event_cursor if self.event_selection_mode else 0
        event = day_events[idx]

        if event.description:
            # Prompt with y/n/d when event has a description
            prompt = f"Delete '{event.summary}'? (y/N/d=description only): "
            try:
                stdscr.addstr(height - 1, 0,
                              prompt[:width - 1].ljust(width - 1),
                              curses.A_BOLD)
                stdscr.refresh()
                ch = stdscr.getch()
            except curses.error:
                return
            if ch in (ord("d"), ord("D")):
                event.description = None
                write_ics(self.ics_path, self.events)
                return
            elif ch not in (ord("y"), ord("Y")):
                return
        else:
            confirmed = self._prompt_yn(
                stdscr,
                f"Delete '{event.summary}'? (y/N): ",
                height - 1, width,
            )
            if not confirmed:
                return

        self.events.remove(event)
        write_ics(self.ics_path, self.events)
        self.event_cursor = max(0, self.event_cursor - 1)
        remaining = [e for e in self.events if e.date_in_tz(self.timezone) == day_date]
        if not remaining:
            self.event_selection_mode = False

    def _change_timezone(self, stdscr, height, width):
        # Prompt the user for a new IANA timezone and save it to config
        prompt_y = height - 1
        tz_str = self._prompt(
            stdscr,
            f"Timezone [{self.timezone}]: ",
            prompt_y, width,
        )
        if tz_str is None or not tz_str.strip():
            return
        tz_str = tz_str.strip()
        # Validate using zoneinfo
        try:
            ZoneInfo(tz_str)
        except (ZoneInfoNotFoundError, KeyError):
            try:
                stdscr.addstr(
                    prompt_y, 0,
                    f"Invalid timezone: {tz_str!r}"[:width - 1].ljust(width - 1),
                    curses.A_BOLD,
                )
                stdscr.refresh()
                stdscr.getch()
            except curses.error:
                pass
            return
        self.timezone = tz_str
        self.config["timezone"] = tz_str
        save_config(self.config)
