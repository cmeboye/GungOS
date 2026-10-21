"""Placeholder pages now; engineering values and result tables later."""


def _wrapped(value, width):
    words = value.split()
    line = ''
    for word in words:
        if line and len(line)+len(word)+1 > width:
            yield line
            line = ''
        if len(word) > width:
            if line:
                yield line
                line = ''
            while len(word) > width:
                yield word[:width]
                word = word[width:]
        line = line+' '+word if line else word
    if line:
        yield line


def show_placeholder(draw, tool):
    """Make the planned status explicit; do not present fabricated results."""
    from . import theme
    draw.fill_screen(theme.BG)
    limit = theme.columns(draw, int(draw.size.x)-24)
    theme.text(draw, 12, 35, tool['title'], theme.ACCENT)
    theme.text(draw, 12, 55, 'Planned - not implemented', theme.MUTED)
    y = 82
    for line in _wrapped(tool['description'], limit):
        theme.text(draw, 12, y, line)
        y += 15
    y += 12
    theme.text(draw, 12, y, 'Planned outputs', theme.ACCENT)
    y += 19
    for value in tool['planned_outputs']:
        for line in _wrapped('- '+value, limit):
            if y >= int(draw.size.y)-theme.FOOT_HEIGHT-14:
                break
            theme.text(draw, 12, y, line, theme.MUTED)
            y += 15
    theme.chrome(draw, 'placeholder', 'Tool structure is ready')
    draw.swap()


def show_result(view_manager, result):
    """Display values, units, assumptions, convergence status and plot choices."""
    raise NotImplementedError('Engineering result display is a placeholder')
