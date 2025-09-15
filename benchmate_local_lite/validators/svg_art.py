import re
import xml.etree.ElementTree as ET
from datetime import datetime

SVG_OPEN_RE = re.compile(r"<svg[\s\\S]*?>", re.IGNORECASE)
SVG_BLOCK_RE = re.compile(r"(<svg.*>.*</svg>)", re.IGNORECASE)

def strip_code_fences(text: str) -> str:
    s = text.strip()
    # Strip ``` or ```xml fences if present
    if s.startswith("```"):
        s = s.split("```", 2)
        if len(s) == 3:
            return s[1].split("\n", 1)[-1] if s[1].strip().isalpha() else s[1]
    return text

def extract_svg(text: str) -> str | None:
    """
    Try to extract the first <svg>...</svg> block, ignoring code fences.
    """
    s = strip_code_fences(text)
    s = s.replace("\n", "")
    m = SVG_BLOCK_RE.search(s)
    if not m:
        # Sometimes models prepend XML declaration; keep it if present
        # but ensure an <svg> block exists
        return None
    return m.group(1)

def validate_svg_art(svg_text: str) -> tuple[bool, str]:
    """
    Very lightweight validation: parses as XML, root is <svg>,
    must contain <title> and <desc>, and at least one of <path|circle|rect|ellipse|polygon|polyline>.
    """
    try:
        root = ET.fromstring(svg_text)
    except Exception as e:
        return False, f"XML parse error: {e}"

    if not root.tag.lower().endswith("svg"):
        return False, "Root element is not <svg>."

    # Check for title & desc presence and relevant keywords (pelican, bicycle)
    title = None
    desc = None
    shapes = 0
    for el in root.iter():
        tag = el.tag.split('}')[-1].lower()
        if tag == "title" and (el.text or "").strip():
            title = el.text.strip()
        if tag == "desc" and (el.text or "").strip():
            desc = el.text.strip()
        if tag in {"path","circle","rect","ellipse","polygon","polyline","line"}:
            shapes += 1

    if not title:
        return False, "Missing <title>."
    if not desc:
        return False, "Missing <desc>."
    dlow = (desc or "").lower() + " " + (title or "").lower()
    if not ("pelican" in dlow and ("bicycle" in dlow or "bike" in dlow)):
        return False, "Title/desc should mention pelican and bicycle."

    if shapes == 0:
        return False, "No drawable elements found (path/circle/rect/etc.)."

    return True, "OK"

def insert_metadata_comment(svg_text: str, metadata: dict) -> str:
    """
    Insert an XML comment with metadata immediately after the opening <svg> tag.
    """
    comment_lines = ["<!-- BenchMate metadata:"]
    for k, v in metadata.items():
        comment_lines.append(f"  {k}: {v}")
    comment_lines.append("-->")
    comment = "\\n".join(comment_lines)

    def repl(m):
        open_tag = m.group(0)
        return f"{open_tag}\\n{comment}\\n"

    return SVG_OPEN_RE.sub(repl, svg_text, count=1)