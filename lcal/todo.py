import os
import re

from lcal.config import TODO_DIR

# Mapping used in filenames
COLOUR_SHORT = {
    "COLOR_RED": "r",
    "COLOR_GREEN": "g",
    "COLOR_YELLOW": "y",
    "COLOR_BLUE": "b",
    "COLOR_MAGENTA": "m",
    "COLOR_CYAN": "c",
    "COLOR_WHITE": "w",
    "COLOR_BLACK": "k",
}

# Reverse mapping
COLOUR_FROM_SHORT = {v: k for k, v in COLOUR_SHORT.items()}


class TodoItem:
    def __init__(self, name, priority, filepath, colour=None):
        self.name = name
        self.priority = priority
        self.filepath = filepath
        self.colour = colour


def load_todos(extension="md"):
    os.makedirs(TODO_DIR, exist_ok=True)
    items = []
    ext = re.escape(extension)
    shorts = "|".join(re.escape(s) for s in COLOUR_FROM_SHORT)
    # Format: {priority}_{name}_{short}.ext
    pattern = re.compile(rf"^(\d)_(.+?)(?:_({shorts}))?\.{ext}$")
    for filename in os.listdir(TODO_DIR):
        # Ignore files that does not end with chosen extension
        if not filename.endswith(f".{extension}"):
            continue
        try:
            # Parse todo file name
            match = pattern.match(filename)
            priority = int(match.group(1))
            name = match.group(2)
            # None if no colour
            colour = COLOUR_FROM_SHORT.get(match.group(3)) if match and match.lastindex >= 3 else None
            filepath = os.path.join(TODO_DIR, filename)
            # Add todo items with their properties
            items.append(TodoItem(name, priority, filepath, colour))
        except:
            print("Clean up incorrectly formatted todo files.")
            os._exit(1)
    items.sort(key=lambda t: t.priority)
    return items


def add_todo(name, priority, colour=None, extension="md"):
    os.makedirs(TODO_DIR, exist_ok=True)
    colour_suffix = f"_{COLOUR_SHORT[colour]}" if colour and colour in COLOUR_SHORT else ""
    filename = f"{priority}_{name}{colour_suffix}.{extension}"
    filepath = os.path.join(TODO_DIR, filename)
    # Create an empty file (colour is in the filename, not the content)
    with open(filepath, "w") as f:
        f.write("")
    return TodoItem(name, priority, filepath, colour)


def delete_todo(item):
    if os.path.exists(item.filepath):
        os.remove(item.filepath)


def change_todo_priority(item, new_priority):
    # Priority can only be 1-9
    new_priority = max(1, min(9, new_priority))
    basename = os.path.basename(item.filepath)
    # Replace the leading priority digit
    new_basename = f"{new_priority}_{basename[2:]}"
    new_filepath = os.path.join(os.path.dirname(item.filepath), new_basename)
    # Rename the file
    if item.filepath != new_filepath:
        os.rename(item.filepath, new_filepath)
    item.priority = new_priority
    item.filepath = new_filepath
    return item


def rename_todo(item, new_name):
    colour_suffix = f"_{COLOUR_SHORT[item.colour]}" if item.colour and item.colour in COLOUR_SHORT else ""
    _, ext = os.path.splitext(item.filepath)
    new_basename = f"{item.priority}_{new_name}{colour_suffix}{ext}"
    new_filepath = os.path.join(os.path.dirname(item.filepath), new_basename)
    if item.filepath != new_filepath:
        os.rename(item.filepath, new_filepath)
    item.name = new_name
    item.filepath = new_filepath
    return item


def set_todo_colour(item, colour):
    colour_suffix = f"_{COLOUR_SHORT[colour]}" if colour and colour in COLOUR_SHORT else ""
    _, ext = os.path.splitext(item.filepath)
    new_basename = f"{item.priority}_{item.name}{colour_suffix}{ext}"
    new_filepath = os.path.join(os.path.dirname(item.filepath), new_basename)
    if item.filepath != new_filepath:
        os.rename(item.filepath, new_filepath)
    item.colour = colour
    item.filepath = new_filepath
    return item
