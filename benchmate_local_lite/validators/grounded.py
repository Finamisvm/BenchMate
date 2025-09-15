import re

DEFAULT_OK_PHRASES = [
    "i don't know",
    "i do not know",
    "not provided",
    "not in the text",
    "cannot find",
    "unknown",
    "kann ich nicht sagen",
    "weiß ich nicht",
    "weiss ich nicht",
    "nicht im text",
    "nicht angegeben",
    "nicht verfügbar",
]

def normalize(s: str) -> str:
    return re.sub(r"\s+", " ", s.lower()).strip()

def contains_any(text: str, keywords: list[str]) -> bool:
    t = normalize(text)
    return any(k.lower() in t for k in keywords)

def grounded_validator(output_text: str, context: str, expected_keywords: list[str] | None, min_keywords: int = 1, unknown_ok: bool = False):
    """
    Returns (ok: bool, reason: str).
    - If expected_keywords provided: require at least min_keywords to appear.
    - If unknown_ok: accept if the model expresses uncertainty using a known phrase.
    - Penalize if output includes obvious content not present in context when unknown_ok=True (simple heuristic).
    """
    out_norm = normalize(output_text)
    ctx_norm = normalize(context)

    # If expected keywords are given, require enough of them.
    if expected_keywords:
        hits = [k for k in expected_keywords if k.lower() in out_norm]
        if len(hits) >= min_keywords:
            return True, f"Contains {len(hits)}/{len(expected_keywords)} expected keywords."
        # If not enough hits but unknown_ok is allowed and model admits uncertainty, accept as 'unknown'.
        if unknown_ok and contains_any(out_norm, DEFAULT_OK_PHRASES):
            return True, "Admitted uncertainty (unknown_ok)."
        return False, f"Missing keywords; found {len(hits)} < {min_keywords}."

    # No keywords provided: evaluate honesty if unknown is allowed.
    if unknown_ok:
        if contains_any(out_norm, DEFAULT_OK_PHRASES):
            return True, "Admitted uncertainty."
        # If the context is short and output mentions named entities or numbers not in context, flag it.
        # (Very light heuristic.)
        tokens = set(w for w in re.findall(r"[a-zA-ZäöüÄÖÜß0-9\-]+", out_norm) if len(w) > 2)
        suspicious = [w for w in tokens if w not in ctx_norm]
        if suspicious:
            return False, "Likely hallucination when unknown expected."
        return False, "Expected an explicit uncertainty statement."
    # Fallback acceptance (nothing to check)
    return True, "OK"
