#!/usr/bin/env python3
"""Check that local links and assets in the static site point to existing files."""
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
HTML_FILES = sorted(ROOT.rglob("*.html"))
SKIP_DIRS = {".git", ".github"}


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


def target_for(document: Path, url: str):
    parts = urlsplit(url)
    if parts.scheme or parts.netloc or not parts.path:
        return None
    path = Path(unquote(parts.path))
    if path.is_absolute():
        candidate = ROOT / path.relative_to("/")
    else:
        candidate = document.parent / path
    candidate = candidate.resolve()
    try:
        candidate.relative_to(ROOT)
    except ValueError:
        return f"escapes repository: {url}"
    if candidate.is_dir():
        candidate = candidate / "index.html"
    return None if candidate.exists() else f"missing local target: {url}"


def main():
    errors = []
    for document in HTML_FILES:
        parser = References()
        try:
            parser.feed(document.read_text(encoding="utf-8"))
        except (OSError, UnicodeError) as exc:
            errors.append(f"{document.relative_to(ROOT)}: cannot read HTML: {exc}")
            continue
        for url in parser.values:
            problem = target_for(document, url)
            if problem:
                errors.append(f"{document.relative_to(ROOT)}: {problem}")
    if errors:
        print("Static site checks found broken local references:")
        print("\n".join(f"- {error}" for error in errors))
        return 1
    print(f"Checked local references in {len(HTML_FILES)} HTML files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
