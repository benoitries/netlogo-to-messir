import re
from pathlib import Path
from typing import Set


_RULE_ID_PATTERN = re.compile(r"<(?P<id>[A-Z]{3}\d+-[A-Z0-9\-]+)>.*?</(?P=id)>", re.DOTALL)


def parse_rule_ids(rules_md_path: str | Path) -> Set[str]:
    """Parse RULE IDs enclosed in <RULE-ID>...</RULE-ID> blocks from a RULES_LUCIM md file.

    Returns a set of IDs like LOM1-..., LDR8-..., LSC3-...
    """
    p = Path(rules_md_path)
    text = p.read_text(encoding="utf-8")
    ids: Set[str] = set(m.group("id").strip() for m in _RULE_ID_PATTERN.finditer(text))
    return ids
