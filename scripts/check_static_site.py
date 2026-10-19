#!/usr/bin/env python3
"""Fail-closed static-site reference checker for an explicitly configured publish tree."""
import argparse
from html.parser import HTMLParser
import os
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
EXCLUDED_DIR_NAMES = {
    ".git", ".github", "private", "tts-13", "floor-13", "floor13",
    "protected", "deck-level",
}


class References(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.values = []

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        for key in ("href", "src", "poster"):
            value = attributes.get(key)
            if value:
                self.values.append(value.strip())


def resolve_publish_root(repo_root, configured):
    if not configured or not configured.strip():
        raise ValueError("missing publish root")
    repo_root = Path(repo_root).resolve()
    candidate = Path(configured)
    if not candidate.is_absolute():
        candidate = repo_root / candidate
    try:
        resolved = candidate.resolve(strict=True)
    except (OSError, RuntimeError):
        raise ValueError("invalid publish root") from None
    try:
        resolved.relative_to(repo_root)
    except ValueError:
        raise ValueError("publish root outside repository") from None
    if not resolved.is_dir() or resolved.name.casefold() in EXCLUDED_DIR_NAMES:
        raise ValueError("invalid publish root")
    return resolved


def collect_html_files(publish_root):
    documents = []
    unsafe_documents = 0
    for current, dirs, files in os.walk(publish_root, followlinks=False):
        current_path = Path(current)
        dirs[:] = sorted(
            name for name in dirs
            if name.casefold() not in EXCLUDED_DIR_NAMES
            and not (current_path / name).is_symlink()
        )
        for name in sorted(files):
            if not name.lower().endswith(".html"):
                continue
            document = current_path / name
            if document.is_symlink():
                unsafe_documents += 1
                continue
            try:
                document.resolve(strict=True).relative_to(publish_root)
            except (OSError, RuntimeError, ValueError):
                unsafe_documents += 1
                continue
            documents.append(document)
    return documents, unsafe_documents


def target_is_invalid(document, url, publish_root):
    parts = urlsplit(url)
    if parts.scheme or parts.netloc or not parts.path:
        return False
    decoded_path = unquote(parts.path)
    if "\x00" in decoded_path:
        return True
    if decoded_path.startswith("/"):
        candidate = publish_root / decoded_path.lstrip("/")
    else:
        candidate = document.parent / decoded_path
    try:
        candidate = candidate.resolve(strict=False)
        candidate.relative_to(publish_root)
    except (OSError, RuntimeError, ValueError):
        return True
    if candidate.is_dir():
        candidate = candidate / "index.html"
        try:
            candidate = candidate.resolve(strict=False)
            candidate.relative_to(publish_root)
        except (OSError, RuntimeError, ValueError):
            return True
    return not candidate.exists()


def check_site(publish_root):
    documents, unsafe_documents = collect_html_files(publish_root)
    invalid_references = 0
    unreadable_documents = 0
    for document in documents:
        parser = References()
        try:
            parser.feed(document.read_text(encoding="utf-8"))
        except (OSError, UnicodeError):
            unreadable_documents += 1
            continue
        invalid_references += sum(
            1 for url in parser.values if target_is_invalid(document, url, publish_root)
        )
    return {
        "documents": len(documents),
        "invalid_references": invalid_references,
        "unreadable_documents": unreadable_documents,
        "unsafe_documents": unsafe_documents,
    }


def main(argv=None, repo_root=ROOT):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--publish-root",
        default=os.environ.get("PUBLIC_SITE_ROOT", ""),
        help=argparse.SUPPRESS,
    )
    args = parser.parse_args(argv)
    try:
        publish_root = resolve_publish_root(repo_root, args.publish_root)
    except ValueError:
        print("Static site checks blocked: configure PUBLIC_SITE_ROOT to a verified directory within the repository.")
        return 2

    result = check_site(publish_root)
    problems = (
        result["invalid_references"]
        + result["unreadable_documents"]
        + result["unsafe_documents"]
    )
    if problems:
        print(
            "Static site checks failed: "
            f"{result['invalid_references']} invalid local references, "
            f"{result['unreadable_documents']} unreadable documents, "
            f"{result['unsafe_documents']} unsafe document paths."
        )
        return 1
    print(f"Static site checks passed for {result['documents']} HTML files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
