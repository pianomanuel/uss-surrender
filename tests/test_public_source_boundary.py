import importlib.util
from pathlib import Path
import unittest

SCRIPT = Path(__file__).parents[1] / "scripts" / "check_public_source_boundary.py"
spec = importlib.util.spec_from_file_location("check_public_source_boundary", SCRIPT)
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)


class PublicSourceBoundaryTests(unittest.TestCase):
    def test_ordinary_public_paths_pass(self):
        paths = ["index.html", "assets/site.css", "docs/floor-plan.html", "scripts/build.py"]
        self.assertEqual([], checker.check_paths(paths))

    def test_restricted_directory_segment_fails_with_generic_diagnostic(self):
        for path in ("synthetic/TTS-13/chapter.txt", "synthetic/floor_13/notes.txt", "synthetic/deck13/source.html"):
            with self.subTest(path_kind=path.split("/")[1]):
                errors = checker.check_paths(["index.html", path])
                self.assertEqual(["restricted_source_tracked"], errors)
                self.assertNotIn(path, " ".join(errors))

    def test_restricted_filename_prefix_fails(self):
        for path in ("synthetic/tts-13-example.txt", "synthetic/floor13-draft.html", "synthetic/deck-13-notes.md"):
            with self.subTest(path_kind=path.split("/")[-1].split("-")[0]):
                self.assertEqual(["restricted_source_tracked"], checker.check_paths([path]))

    def test_backslash_paths_are_normalized(self):
        self.assertEqual(["restricted_source_tracked"], checker.check_paths([r"synthetic\\floor_13\\note.txt"]))

    def test_diagnostics_never_include_paths(self):
        candidate = "synthetic/TTS-13/PRIVATE_MARKER.txt"
        errors = checker.check_paths([candidate])
        self.assertNotIn("PRIVATE_MARKER", " ".join(errors))
        self.assertNotIn(candidate, " ".join(errors))


if __name__ == "__main__":
    unittest.main()
