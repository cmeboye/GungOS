"""8x8 PicoDESK app icons for the header: 'A' accent, 'T' text, '.' clear."""

EGGCEL = (
    'AATAATAA',
    'AATAATAA',
    'TTTTTTTT',
    'AATAATAA',
    'AATAATAA',
    'TTTTTTTT',
    'AATAATAA',
    'AATAATAA',
)

# A page with a W, after the familiar word-processor badge.
PICOWORD = (
    'AAAAAAAA',
    'ATTTTTTA',
    'AATTTTAA',
    'AATTTTAA',
    'AATAATAA',
    'ATATTATA',
    'ATTTTTTA',
    'AAAAAAAA',
)

# A pencil: eraser at the top right, point at the bottom left.
PICOPAINT = (
    '......AA',
    '.....AAA',
    '....TAA.',
    '...TTT..',
    '..TTT...',
    '.TTT....',
    'ATT.....',
    'AA......',
)


def page_name(page):
    """'plot_setup' -> 'Plot setup', for the header path."""
    text=page.replace('_',' ')
    return text[:1].upper()+text[1:]


# Status strip, then the 18-pixel header: content starts here.
TOP = 16 + 18
