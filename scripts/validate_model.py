#!/usr/bin/env python3
"""Validate that a model name is accepted by its API provider before running.

Usage:
  python scripts/validate_model.py --model <model_name>

Exit codes:
  0 = OK
  1 = Invalid/missing API key
  2 = Model/provider connectivity error (e.g., unsupported model)
  3 = Bad usage
"""

import argparse
import sys
from pathlib import Path

# Ensure repository modules are importable
sys.path.append(str(Path(__file__).resolve().parents[1]))

from utils_openai_client import validate_model_name_and_connectivity  # noqa: E402
from utils_api_key import load_env_files  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Preflight validate model/provider")
    parser.add_argument("--model", required=True, help="Model name to validate")
    args = parser.parse_args()

    load_env_files()
    ok, provider, message = validate_model_name_and_connectivity(args.model, verbose=True)
    if ok:
        sys.exit(0)
    # Distinguish key vs connectivity errors by prefix
    if message.lower().startswith("api key error"):
        sys.exit(1)
    sys.exit(2)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:
        print(f"Unexpected error: {type(e).__name__}: {e}")
        sys.exit(3)


