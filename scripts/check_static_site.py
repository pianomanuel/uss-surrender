#!/usr/bin/env python3
"""Fail-closed local-reference checker for an explicitly allowlisted publish tree.

The manifest is intentionally required. The checker never discovers HTML in the
repository as a whole and never prints paths, URLs, or exception details.
"""
from __future__ import annotations

import argparse
import json
import os
from html.parser import HTMLParser
from pathlib import Path, PurePosixPath
from urllib.parse import unquote, urlsplit

DEFAULT_MANIFEST = ".github/publish-manifest.json"

# Defense in depth: known restricted source namespaces must never be allowlisted.
# This is not a substitute for keeping restricted source out of a public repository.
_RESERVED_PUBLISH_NAMES = {"tts", "tts-13", "floor13", "floor-13", "deck13", "deck-13"}
_RESERVED_PUBLISH_PREFIXES = (
    "deck13-", "deck-13-", "floor13-", "floor-13-", "tts-13-",
)


def _is_reserved_publish_path(path: PurePosixPath) -> bool:
    """Reject known restricted-source names anywhere in a proposed public path."""
    for part in path.parts:
        normalized = part.casefold().replace("_", "-").replace(" ", "-")
        stem = Path(normalized).stem
        if normalized in _RESERVED_PUBLISH_NAMES or stem in _RESERVED_PUBLISH_NAMES:
            return True
        if normalized.startswith(_RESERVED_PUBLISH_PREFIXES) or stem.startswith(_RESERVED_PUBLISH_PREFIXES):
            return True
    return False


class References(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.values: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        attributes = dict(attrs)
        for key in ("href", "src", "poster"):
            value = attributes.get(key)
            if value:
                self.values.append(value.strip())


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _has_symlink_component(base: Path, path: Path) -> bool:
    """Check lexical path components without opening their targets."""
    try:
        relative = path.relative_to(base)
    except ValueError:
        return True
    current = base
    if current.is_symlink():
        return True
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            return True
    return False


def _safe_relative(value: object) -> PurePosixPath | None:
    if not isinstance(value, str) or not value or "\\" in value or "\x00" in value:
        return None
    if value.startswith("/"):
        return None
    parts = value.split("/")
    if any(part in ("", ".", "..") for part in parts):
        return None
    path = PurePosixPath(value)
    if path.is_absolute() or not path.parts:
        return None
    return path


def _read_manifest(repo_root: Path, manifest_path: Path):
    try:
        manifest_abs = manifest_path if manifest_path.is_absolute() else repo_root / manifest_path
        if not _is_within(manifest_abs.resolve(), repo_root) or _has_symlink_component(repo_root, manifest_abs):
            return None, "manifest_invalid"
        if not manifest_abs.is_file():
            return None, "manifest_missing"
        data = json.loads(manifest_abs.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError, RuntimeError, ValueError):
        return None, "manifest_invalid"
    if not isinstance(data, dict) or data.get("version") != 1:
        return None, "manifest_invalid"
    root_rel = _safe_relative(data.get("publish_root"))
    files = data.get("files")
    if root_rel is None or not isinstance(files, list) or not files:
        return None, "manifest_invalid"
    if _is_reserved_publish_path(root_rel):
        return None, "manifest_invalid"
    # Never treat Git metadata or CI configuration as a publish root.
    if any(part.casefold() in {".git", ".github"} for part in root_rel.parts):
        return None, "manifest_invalid"
    file_paths: list[PurePosixPath] = []
    seen: set[str] = set()
    for raw in files:
        rel = _safe_relative(raw)
        if rel is None or _is_reserved_publish_path(rel) or str(rel) in seen:
            return None, "manifest_invalid"
        seen.add(str(rel))
        file_paths.append(rel)
    return {"root_rel": root_rel, "files": file_paths}, None


def _resolve_reference_path(base: Path, raw_path: str, publish_root: Path) -> Path | None:
    """Normalize a local URL path while rejecting symlink and root escapes."""
    if "\\" in raw_path or "\x00" in raw_path:
        return None
    current = base
    for part in raw_path.split("/"):
        if part in ("", "."):
            continue
        if part == "..":
            if current == publish_root:
                return None
            current = current.parent
            continue
        current = current / part
        if current.is_symlink():
            return None
    try:
        resolved = current.resolve(strict=False)
    except (OSError, RuntimeError):
        return None
    if not _is_within(resolved, publish_root):
        return None
    return resolved


def _target_for(document: Path, url: str, publish_root: Path, manifest_files: set[str]):
    try:
        parts = urlsplit(url)
    except ValueError:
        return "reference_invalid"
    if parts.scheme or parts.netloc or not parts.path:
        return None
    try:
        decoded = unquote(parts.path, errors="strict")
    except (UnicodeDecodeError, ValueError):
        return "reference_invalid"
    absolute = decoded.startswith("/")
    if absolute:
        decoded = decoded.lstrip("/")
    if not decoded:
        decoded = "index.html"
        absolute = True
    base = publish_root if absolute else document.parent
    candidate = _resolve_reference_path(base, decoded, publish_root)
    if candidate is None:
        return "reference_invalid"
    if candidate.is_dir():
        candidate = candidate / "index.html"
    try:
        candidate_rel = candidate.relative_to(publish_root).as_posix()
    except ValueError:
        return "reference_invalid"
    if candidate_rel not in manifest_files or not candidate.is_file():
        return "reference_missing_or_unlisted"
    return None


def check_site(repo_root: Path, manifest_path: Path) -> list[str]:
    """Return sanitized error categories only; never include a path or URL."""
    if repo_root.is_symlink():
        return ["checkout_root_invalid"]
    try:
        repo_root = repo_root.resolve(strict=True)
    except (OSError, RuntimeError):
        return ["checkout_root_invalid"]
    if not repo_root.is_dir():
        return ["checkout_root_invalid"]

    manifest, manifest_error = _read_manifest(repo_root, manifest_path)
    if manifest_error:
        return [manifest_error]

    publish_root = repo_root / Path(*manifest["root_rel"].parts)
    try:
        root_resolved = publish_root.resolve(strict=True)
    except (OSError, RuntimeError):
        return ["publish_root_invalid"]
    if root_resolved == repo_root or not _is_within(root_resolved, repo_root) or not root_resolved.is_dir():
        return ["publish_root_invalid"]
    if _has_symlink_component(repo_root, publish_root):
        return ["publish_root_invalid"]
    publish_root = root_resolved

    allowed: set[str] = set()
    for rel in manifest["files"]:
        candidate = publish_root / Path(*rel.parts)
        if _has_symlink_component(publish_root, candidate):
            return ["manifest_invalid"]
        try:
            resolved = candidate.resolve(strict=True)
        except (OSError, RuntimeError):
            return ["manifest_invalid"]
        if not _is_within(resolved, publish_root) or not resolved.is_file():
            return ["manifest_invalid"]
        allowed.add(rel.as_posix())

    # Walk only inside the explicitly approved publish root, never the repo root.
    actual: set[str] = set()
    try:
        for current, dirs, names in os.walk(publish_root, followlinks=False):
            current_path = Path(current)
            for dirname in list(dirs):
                if (current_path / dirname).is_symlink():
                    return ["publish_tree_invalid"]
            for name in names:
                entry = current_path / name
                if entry.is_symlink() or not entry.is_file():
                    return ["publish_tree_invalid"]
                actual.add(entry.relative_to(publish_root).as_posix())
    except (OSError, RuntimeError):
        return ["publish_tree_invalid"]
    if actual != allowed:
        return ["publish_tree_allowlist_mismatch"]

    errors: list[str] = []
    html_files = sorted(p for p in manifest["files"] if p.suffix.lower() in {".html", ".htm"})
    for rel in html_files:
        document = publish_root / Path(*rel.parts)
        try:
            parser = References()
            parser.feed(document.read_text(encoding="utf-8"))
            parser.close()
        except (OSError, UnicodeError, ValueError):
            errors.append("html_unreadable")
            continue
        for url in parser.values:
            problem = _target_for(document, url, publish_root, allowed)
            if problem:
                errors.append(problem)
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", default=DEFAULT_MANIFEST)
    parser.add_argument("--checkout-root", default=str(Path(__file__).resolve().parents[1]))
    args = parser.parse_args()
    errors = check_site(Path(args.checkout_root), Path(args.manifest))
    if errors:
        print("Static publish checks failed closed.")
        for error in sorted(set(errors)):
            print(f"- {error}")
        return 1
    print("Static publish checks passed for the explicit manifest.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
