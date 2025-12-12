import os

def tree(path=".", prefix=""):
    try:
        items = os.listdir(path)
    except Exception as e:
        print(prefix + " [ERR]", e)
        return

    for i, name in enumerate(items):
        full = path + "/" + name if path != "/" else "/" + name
        last = (i == len(items) - 1)

        connector = "└── " if last else "├── "
        print(prefix + connector + name)

        try:
            mode = os.stat(full)[0]
            is_dir = mode & 0x4000   # dir bit in MicroPython
        except:
            is_dir = False

        if is_dir:
            extension = "    " if last else "│   "
            tree(full, prefix + extension)

# Run from root by default
tree("/")