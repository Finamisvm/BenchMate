import json
import re
from jsonschema import validate, ValidationError

def only_json(text: str) -> bool:
    """
    Returns True if the text appears to be ONLY a single JSON object/array, with no extra prose.
    """
    s = text.strip()
    # Quick check: must start with { or [ and end with } or ]
    if not ((s.startswith("{") and s.endswith("}")) or (s.startswith("[") and s.endswith("]"))):
        return False
    # Disallow fence/codeblocks or extra trailing characters beyond a single JSON value
    # Try loading strictly; if it parses and covers the full string, we accept.
    try:
        obj = json.loads(s)
        # re-dump to normalized string and compare structure approximately by attempting a second parse
        # This is a pragmatic check; main safeguard is below in schema validation.
        return True
    except Exception:
        return False

def validate_json_against_schema(text: str, schema: dict):
    """
    Returns (ok: bool, reason: str)
    - ok only if text is pure JSON and validates against the given JSON schema.
    """
    s = text.strip()
    if not only_json(s):
        return False, "Output is not pure JSON (extra text or invalid JSON)."

    try:
        data = json.loads(s)
    except Exception as e:
        return False, f"JSON parse error: {e}"

    try:
        validate(data, schema)
    except ValidationError as e:
        return False, f"Schema violation: {e.message}"
    except Exception as e:
        return False, f"Schema error: {e}"

    return True, "OK"
