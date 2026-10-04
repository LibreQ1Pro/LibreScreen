"""Line breaks at the ends of the words in the fixed texts of a page, measured with the glyph widths of the screen's own fonts.

The screen breaks a long text where the line is full, in the middle of a word. A fixed text (the pages of the start-up and of the shut-down) is known in every
language, so the breaks are put in it: the line break of the screen is the control character CR, written ``\\r`` in the instructions
(``tools/make_fonts.py`` gives that character a glyph, so that a line that ends in it is centred correctly).

Where a language writes no spaces (Chinese, Japanese) a line breaks between any two characters, but not before a closing mark. A word wider than a line is cut.
"""
import unicodedata

from make_fonts import ROLES, Faces

_FACES = {}

# marks that do not begin a line
NOT_AT_LINE_START = set("，。！？、；：）」』”…,.!?;:)]}»")
LINE_BREAK = "\\r"


def width_of(role):
    """A function: the width in pixels of a character in the font of ``role`` (the advance the screen uses)."""
    if role not in _FACES:
        _FACES[role] = Faces(*ROLES[role])
    faces = _FACES[role]

    def width(ch):
        font = faces.get(ch)
        return round(font.getlength(ch)) if font is not None else 0
    return width


def _tokens(text):
    """(token, space before) pairs: a word, or one character of a language without spaces."""
    result, word, space = [], "", False
    for ch in text:
        if ch.isspace():
            if word:
                result.append((word, space))
                word, space = "", False
            space = True
        elif unicodedata.east_asian_width(ch) in ("W", "F"):
            if word:
                result.append((word, space))
                word, space = "", False
            result.append((ch, space))
            space = False
        else:
            word += ch
    if word:
        result.append((word, space))
    return result


def wrap(text, role, limit):
    """``text`` with ``\\r`` at the ends of the words, no line wider than ``limit`` pixels; returns (text, number of lines)."""
    width = width_of(role)

    def measure(s):
        return sum(width(ch) for ch in s)
    lines, current = [], []          # current: [(token, space before)]

    def text_of(tokens):
        return "".join((" " if space and i else "") + token for i, (token, space) in enumerate(tokens))

    for token, space in _tokens(text):
        pieces = [token]
        if measure(token) > limit:   # a word wider than the line
            pieces, piece = [], ""
            for ch in token:
                if piece and measure(piece + ch) > limit:
                    pieces.append(piece)
                    piece = ""
                piece += ch
            pieces.append(piece)
        for index, piece in enumerate(pieces):
            candidate = current + [(piece, space if index == 0 else False)]
            if current and measure(text_of(candidate)) > limit:
                lines.append(current)
                current = [(piece, False)]
                # a closing mark does not begin a line: it takes the last word of the line before with it
                if piece[0] in NOT_AT_LINE_START and len(lines[-1]) > 1:
                    moved = lines[-1].pop()
                    current = [(moved[0], False), (piece, False)]
            else:
                current = candidate
    if current:
        lines.append(current)
    return LINE_BREAK.join(text_of(line) for line in lines), len(lines)
