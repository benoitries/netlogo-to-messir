#!/usr/bin/env python3
"""
Validate that no AI model names are hard-coded outside config.py.

Rules:
- Allowed: model names only in config.py (AVAILABLE_MODELS, MODEL_CONFIG docs/examples allowed).
- Forbidden: occurrences in other .py files within this package.

Exit code:
- 0 if no forbidden occurrences
- 1 with a report printed to stdout otherwise
"""

import os
import re
import sys

PACKAGE_ROOT = os.path.dirname(os.path.abspath(__file__))

# Model-like tokens to search for (broad):
TOKENS = [r"gpt-\d", r"gpt-\d-", r"gpt-5(?:-mini|-nano)?", r"gpt-4", r"gpt-3\.5", r"o3", r"o4-mini"]
PATTERN = re.compile("|".join(TOKENS))

def scan_file(path: str) -> list:
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()
    hits = []
    for i, line in enumerate(lines, 1):
        if PATTERN.search(line):
            hits.append((i, line.rstrip()))
    return hits

def main() -> int:
    violations = []
    for root, _, files in os.walk(PACKAGE_ROOT):
        # Skip virtual envs, site-packages and generated output
        norm = root.replace("\\", "/")
        if "/.venv/" in norm or "/site-packages/" in norm or norm.endswith("/.venv"):
            continue
        if norm.endswith("/output") or "/output/" in norm:
            continue
        for fname in files:
            if not fname.endswith(".py"):
                continue
            path = os.path.join(root, fname)
            # Allow config.py to contain model names only at this single entry point
            base = os.path.basename(path)
            if base in ("config.py", "validate_no_hardcoded_models.py"):
                continue
            hits = scan_file(path)
            if hits:
                violations.append((path, hits))

    if not violations:
        print("OK: No hard-coded AI model names found outside config.py")
        return 0

    print("Forbidden hard-coded AI model names found:")
    for path, hits in violations:
        print(f"- {path}")
        for ln, text in hits[:5]:  # cap for readability
            print(f"  L{ln}: {text}")
        if len(hits) > 5:
            print(f"  ... and {len(hits) - 5} more")
    return 1

if __name__ == "__main__":
    sys.exit(main())


