import re

class RuleState:
    def __init__(self):
        self.used = set()

def parse_letter(output_text: str) -> str | None:
    s = output_text.strip()
    # Accept exactly one lowercase ASCII letter, no punctuation, no quotes.
    if re.fullmatch(r"[a-z]", s):
        return s
    # Also accept if the model returns like: "Guess: a" or in backticks: `a`
    m = re.search(r"\b([a-z])\b", s)
    if m and len(re.sub(r"[^a-z]", "", s)) == 1:
        return m.group(1)
    return None

def hangman_step(output_text: str, state: RuleState):
    """
    Returns (ok: bool, reason: str). Enforces:
      - exactly one new letter per turn
    """
    letter = parse_letter(output_text)
    if not letter:
        return False, "Response must be exactly one lowercase letter."
    if letter in state.used:
        return False, "Repeated letter."
    state.used.add(letter)
    return True, "OK"
