#!/usr/bin/env python3
"""Fail-closed, category-only checks for the public operational log."""
from argparse import ArgumentParser
from pathlib import Path
import re

DEFAULT_FILE = Path(__file__).resolve().parents[1] / "SHIPS_LOG.md"
RULES = (
    ("email address", re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)),
    ("issue identifier", re.compile(r"\b[A-Z][A-Z0-9]{1,9}-\d+\b")),
    ("personal identifier reference", re.compile(r"\b(?:real id|social security|ssn|passport number|date of birth)\b", re.IGNORECASE)),
    ("authentication material reference", re.compile(r"\b(?:password|passphrase|api[\s_-]?key|access token|credential)\b", re.IGNORECASE)),
    ("health-record reference", re.compile(r"\b(?:patient record|medical record|diagnosis|protected health information|phi)\b", re.IGNORECASE)),
    ("location-level reference", re.compile(r"\b(?:floor|deck|level)\s+\d+\b", re.IGNORECASE)),
    ("internal path", re.compile(r"(?:^|\s)/(?:workspace|home|users|private)/\S*", re.IGNORECASE)),
    ("internal operations marker", re.compile(r"\b(?:private lane|marker push|force push|internal workflow|backup mirror)\b", re.IGNORECASE)),
)


def scan_text(text: str) -> list[tuple[int, str]]:
    """Return line numbers and category names only; never return matched text."""
    findings = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        for category, pattern in RULES:
            if pattern.search(line):
                findings.append((line_number, category))
    return findings


def format_findings(findings: list[tuple[int, str]]) -> list[str]:
    return ["Public log check failed:", *[f"- line {line_number}: {category}" for line_number, category in findings]]


def main(argv=None) -> int:
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("path", nargs="?", default=str(DEFAULT_FILE), help="public log file to scan")
    args = parser.parse_args(argv)
    try:
        content = Path(args.path).read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        print("Public log check could not read the configured file; failing closed.")
        return 2
    findings = scan_text(content)
    if findings:
        print("\n".join(format_findings(findings)))
        return 1
    print("Public log check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
