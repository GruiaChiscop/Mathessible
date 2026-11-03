"""Word's clipboard HTML as plain HTML, before either paste conversion reads it (paste_plan).

Word does not write lists, footnotes or equations as HTML has them:

- a list item is a paragraph, `<p class=MsoListParagraphCxSpMiddle style='mso-list:l2 level3 lfo2'>`,
  its marker ("1.", "a)", "-") text in `<![if !supportLists]>...<![endif]>`;
- a footnote reference is `<a href="#_ftn1" name="_ftnref1">`, its note a
  `<div style='mso-element:footnote' id=ftn1>` in a footnote list at the end;
- an equation is OMML in a conditional comment, `<!--[if gte msEquation 12]>...<![endif]-->`,
  then a picture of it for other readers in `<![if !msEquation]>...<![endif]>`.

`plain_word_html` writes the lists as `ul`/`ol` and puts a stand-in (private-use characters) where
each footnote reference and equation was, returning the notes' HTML and the equations' OMML beside it.
Whichever conversion reads the HTML passes the stand-ins through as text, and `with_word_parts` puts
the footnotes (`[^label]`, the notes at the end) and the equations back into its Markdown.
"""

from __future__ import annotations

import html as html_module
import re
from collections.abc import Callable
from dataclasses import dataclass

from mathessible.documents.footnotes import next_label

# Stand-ins: no clipboard text holds these private-use characters.
_EQUATION = ("", "")
_FOOTNOTE = ("", "")
_STAND_IN = re.compile("([])(\\d+)[]")


@dataclass(frozen=True, slots=True)
class WordEquation:
    omml: str
    display: bool  # An equation on its own line (`m:oMathPara`).


@dataclass(frozen=True, slots=True)
class WordParts:
    equations: tuple[WordEquation, ...] = ()
    notes: tuple[tuple[str, str], ...] = ()  # (Word's note number, the note's HTML), in order.


_OMML = re.compile(r"<!--\[if gte msEquation 12\]>(.*?)<!\[endif\]-->", re.DOTALL | re.IGNORECASE)
_REFERENCE = re.compile(r"""<a\b[^>]*\bhref=["']?#_ftn(\d+)["']?[^>]*>.*?</a>""", re.DOTALL | re.IGNORECASE)
_BACK_LINK = re.compile(r"""<a\b[^>]*\bhref=["']?#_ftnref\d+["']?[^>]*>.*?</a>""", re.DOTALL | re.IGNORECASE)
_NOTE = re.compile(r"""<div\b[^>]*mso-element:\s*footnote["';][^>]*\bid=["']?ftn(\d+)["']?[^>]*>""", re.IGNORECASE)
_NOTE_LIST = re.compile(r"""<div\b[^>]*mso-element:\s*footnote-list[^>]*>""", re.IGNORECASE)
_PARAGRAPH = re.compile(r"<p\b([^>]*)>(.*?)</p>", re.DOTALL | re.IGNORECASE)
_LIST_STYLE = re.compile(r"mso-list:\s*(l\d+)\s+level(\d+)", re.IGNORECASE)
_MARKER = re.compile(r"<!\[if !supportLists\]>(.*?)<!\[endif\]>", re.DOTALL | re.IGNORECASE)
# An ordered item's marker: "1.", "a)", "iv.", "(1)"; anything else ("-", "·", "o", "§") is a bullet.
_ORDERED = re.compile(r"\(?(\d+|[a-zA-Z]|[ivxlcdmIVXLCDM]+)[.)]")


def plain_word_html(html: str) -> tuple[str, WordParts]:
    """Word's lists as HTML lists, its footnotes and equations as stand-ins (see the module notes)."""
    if "mso-" not in html and "msEquation" not in html:
        return html, WordParts()
    html, equations = _equations(html)
    html, notes = _footnotes(html)
    return _lists(html), WordParts(tuple(equations), tuple(notes))


def with_word_parts(
    markdown: str,
    parts: WordParts,
    source: str,
    equation: Callable[[WordEquation], str | None],
    note: Callable[[str], str],
) -> str | None:
    """The converted Markdown with its stand-ins written back: `$...$` (`$$...$$` on its own line) from
    `equation` (the equation's source, None when it cannot be converted: then None, and the paste is
    the clipboard's text), and `[^label]` with each note, converted by `note`, after the pasted text.
    Labels are numbers free in `source` and the paste, as Insert Footnote chooses them."""
    converted: dict[int, str] = {}
    for index, found in enumerate(parts.equations):
        text = equation(found)
        if text is None:
            return None
        converted[index] = f"$${text}$$" if found.display else f"${text}$"
    labels: dict[str, str] = {}
    taken = source + "\n" + markdown
    for number, _ in parts.notes:
        label = next_label(taken)
        labels[number] = label
        taken += f"\n[^{label}]"

    def stand_in(match: re.Match[str]) -> str:
        if match.group(1) == _EQUATION[0]:
            return converted.get(int(match.group(2)), "")
        label = labels.get(match.group(2))
        return f"[^{label}]" if label else ""

    result = _STAND_IN.sub(stand_in, markdown)
    definitions = []
    for number, content in parts.notes:
        text = _STAND_IN.sub(stand_in, note(content)).strip()
        # A note's later paragraphs are indented to stay in it.
        definitions.append(f"[^{labels[number]}]: " + text.replace("\n", "\n    ").replace("\n    \n", "\n\n"))
    return result.rstrip() + ("\n\n" + "\n\n".join(definitions) if definitions else "")


def _equations(html: str) -> tuple[str, list[WordEquation]]:
    """Each OMML equation as a stand-in, its picture for other readers left out."""
    equations: list[WordEquation] = []
    pieces: list[str] = []
    position = 0
    for match in _OMML.finditer(html):
        if match.start() < position:
            continue  # Inside the previous equation's picture.
        pieces.append(html[position : match.start()])
        omml = match.group(1)
        if "omath" not in omml.lower():
            pieces.append(match.group(0))
            position = match.end()
            continue
        pieces.append(f"{_EQUATION[0]}{len(equations)}{_EQUATION[1]}")
        equations.append(WordEquation(omml, "omathpara" in omml.lower()))
        position = _after_fallback(html, match.end())
    pieces.append(html[position:])
    return "".join(pieces), equations


def _after_fallback(html: str, position: int) -> int:
    """Past `<![if !msEquation]>...<![endif]>` at `position`, which holds conditional blocks of its own
    (a VML picture in a comment, `<![if !vml]><img><![endif]>`); `position` when there is none."""
    opening = "<![if !msEquation]>"
    start = len(html) - len(html[position:].lstrip())
    if not html.startswith(opening, start):
        return position
    depth, index = 0, start
    while index < len(html):
        if html.startswith("<!--", index):
            end = html.find("-->", index)
            index = len(html) if end < 0 else end + 3
        elif html.startswith("<![if", index):
            depth += 1
            index = html.find("]>", index) + 2
        elif html.startswith("<![endif]>", index):
            depth -= 1
            index += len("<![endif]>")
            if depth == 0:
                return index
        else:
            index += 1
    return position


def _footnotes(html: str) -> tuple[str, list[tuple[str, str]]]:
    """References as stand-ins, the notes' HTML (without their link back) taken out of the page."""
    notes: list[tuple[str, str]] = []
    for match in list(_NOTE.finditer(html)):
        end = _closing_div(html, match.end())
        content = _BACK_LINK.sub("", html[match.end() : end - len("</div>")])
        notes.append((match.group(1), content))
    listing = _NOTE_LIST.search(html)
    if listing:
        html = html[: listing.start()] + html[_closing_div(html, listing.end()) :]
    else:
        for match in reversed(list(_NOTE.finditer(html))):
            html = html[: match.start()] + html[_closing_div(html, match.end()) :]
    numbers = {number for number, _ in notes}
    html = _REFERENCE.sub(
        lambda found: f"{_FOOTNOTE[0]}{found.group(1)}{_FOOTNOTE[1]}" if found.group(1) in numbers else "", html
    )
    return html, notes


def _closing_div(html: str, position: int) -> int:
    """After the `</div>` that closes the div opened just before `position`."""
    depth = 1
    for tag in re.finditer(r"<(/?)div\b[^>]*>", html[position:], re.IGNORECASE):
        depth += -1 if tag.group(1) else 1
        if depth == 0:
            return position + tag.end()
    return len(html)


def _lists(html: str) -> str:
    """Runs of Word's list paragraphs as nested `ul`/`ol`."""
    pieces: list[str] = []
    run: list[tuple[int, bool, int | None, str]] = []  # (level, ordered, start, content) per item.
    position = 0
    run_end = 0
    for match in _PARAGRAPH.finditer(html):
        style = _LIST_STYLE.search(match.group(1))
        if style is None:
            continue
        between = html[run_end : match.start()]
        if run and between.strip():
            pieces.append(_list_html(run))
            run = []
        if not run:
            pieces.append(html[position : match.start()])
        marker_match = _MARKER.search(match.group(2))
        marker = _text(marker_match.group(1)) if marker_match else ""
        content = _MARKER.sub("", match.group(2), count=1)
        ordered = _ORDERED.fullmatch(marker)
        start = int(ordered.group(1)) if ordered and ordered.group(1).isdigit() else None
        run.append((int(style.group(2)), bool(ordered), start, content))
        position = run_end = match.end()
    if run:
        pieces.append(_list_html(run))
    pieces.append(html[position:])
    return "".join(pieces)


def _list_html(items: list[tuple[int, bool, int | None, str]]) -> str:
    """Nested lists: an item one level deeper opens a list inside the item before it."""
    out: list[str] = []
    open_lists: list[tuple[int, bool]] = []  # (level, ordered), outermost first; each has an open <li>.
    for level, ordered, start, content in items:
        while open_lists and open_lists[-1][0] > level:
            out.append("</li></ol>" if open_lists.pop()[1] else "</li></ul>")
        if open_lists and open_lists[-1][0] == level and open_lists[-1][1] != ordered:
            out.append("</li></ol>" if open_lists.pop()[1] else "</li></ul>")
        if open_lists and open_lists[-1][0] == level:
            out.append("</li>")
        else:
            first = f' start="{start}"' if ordered and start not in (None, 1) else ""
            out.append(f"<ol{first}>" if ordered else "<ul>")
            open_lists.append((level, ordered))
        out.append(f"<li>{content}")
    while open_lists:
        out.append("</li></ol>" if open_lists.pop()[1] else "</li></ul>")
    return "".join(out)


def _text(fragment: str) -> str:
    """A fragment's text alone, its spaces (Word pads markers with no-break spaces) left out."""
    return "".join(html_module.unescape(re.sub(r"<[^>]*>", "", fragment)).split())
