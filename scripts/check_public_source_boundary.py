#!/usr/bin/env python3
"""Fail-closed path-only audit for restricted source in a public checkout.

This check inspects tracked path names only. It never opens file contents and
never prints matching paths, URLs, or exception details. It is a CI tripwire,
not a substitute for private storage or Git-history remediation.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import PurePosixPath

_RESERVED_NAMES = {
    "tts-13", "tts13", "floor13", "floor-13", "deck13", "deck-13",
}
_RESERVED_PREFIXES = (
    "tts-13-", "tts13-", "floor13-", "floor-13-", "deck13-", "deck-13-",
)


def _is_restricted_path(raw_path: str) -> bool:
    normalized_path = raw_path.replace("\\", "/")
    for part in PurePosixPath(normalized_path).parts:
        normalized = part.casefold().replace("_", "-").replace(" ", "-")
        stem = PurePosixPath(normalized).stem
        if normalized in _RESERVED_NAMES or stem in _RESERVED_NAMES:
            return True
        if normalized.startswith(_RESERVED_PREFIXES) or stem.startswith(_RESERVED_PREFIXES):
            return True
    return False


def check_paths(paths: list[str]) -> list[str]:
    """Return safe diagnostic categories only; never return a matched path."""
    if any(_is_restricted_path(path) for path in paths):
        return ["restricted_source_tracked"]
    return []


def main() -> int:
    try:
        completed = subprocess.run(
            ["git", "ls-files", "-z"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
        paths = [item.decode("utf-8", errors="strict") for item in completed.stdout.split(b"\0") if item]
    except (OSError, subprocess.CalledProcessError, UnicodeDecodeError):
        print("Public source-boundary check failed closed.")
        print("- inventory_unavailable")
        return 1

    errors = check_paths(paths)
    if errors:
        print("Public source-boundary check failed closed.")
        for error in errors:
            print(f"- {error}")
        return 1
    print("Public source-boundary path audit passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
