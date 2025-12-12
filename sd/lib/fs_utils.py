import os


def is_dir(path):
    """Return True if path is a directory, False otherwise."""
    try:
        mode = os.stat(path)[0]
        # MicroPython: directory bit is 0x4000
        return (mode & 0x4000) != 0
    except Exception:
        return False


def normalize(path):
    """Normalize a path, resolving '.' and '..'."""
    parts = []
    for part in path.split("/"):
        if part == "" or part == ".":
            continue
        if part == "..":
            if parts:
                parts.pop()
            continue
        parts.append(part)
    return "/" + "/".join(parts)


def print_tree(root, prefix=""):
    """Recursive tree print of a directory."""
    try:
        entries = os.listdir(root)
    except Exception:
        print(prefix + "[ERR]: " + root)
        return

    print(prefix + root)
    for name in entries:
        full = root + "/" + name
        if is_dir(full):
            print_tree(full, prefix + "  ")
        else:
            print(prefix + "  " + name)
