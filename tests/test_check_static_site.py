import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).parents[1] / "scripts" / "check_static_site.py"
spec = importlib.util.spec_from_file_location("check_static_site", SCRIPT)
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)


class PublishManifestTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name)
        (self.repo / ".github").mkdir()
        self.publish = self.repo / "public-site"
        self.publish.mkdir()
        (self.publish / "index.html").write_text('<a href="about.html">About</a>', encoding="utf-8")
        (self.publish / "about.html").write_text("ok", encoding="utf-8")
        self.manifest = self.repo / ".github" / "publish-manifest.json"
        self.write_manifest(["index.html", "about.html"])

    def tearDown(self):
        self.temp.cleanup()

    def write_manifest(self, files, root="public-site"):
        self.manifest.write_text(
            json.dumps({"version": 1, "publish_root": root, "files": files}),
            encoding="utf-8",
        )

    def test_valid_manifest_and_local_links_pass(self):
        self.assertEqual([], checker.check_site(self.repo, self.manifest))

    def test_missing_manifest_fails_closed_without_path_details(self):
        errors = checker.check_site(self.repo, self.repo / ".github" / "missing.json")
        self.assertEqual(["manifest_missing"], errors)
        self.assertNotIn("missing.json", " ".join(errors))

    def test_missing_publish_root_fails_closed(self):
        self.write_manifest(["index.html"], root="not-created")
        self.assertEqual(["publish_root_invalid"], checker.check_site(self.repo, self.manifest))

    def test_repository_root_is_not_an_allowed_publish_root(self):
        self.write_manifest(["index.html"], root=".")
        self.assertEqual(["manifest_invalid"], checker.check_site(self.repo, self.manifest))

    def test_path_traversal_in_manifest_is_rejected(self):
        self.write_manifest(["../private.txt"])
        self.assertEqual(["manifest_invalid"], checker.check_site(self.repo, self.manifest))

    def test_unlisted_file_fails_without_disclosing_its_name(self):
        (self.publish / "restricted-note.txt").write_text("synthetic-private-marker", encoding="utf-8")
        errors = checker.check_site(self.repo, self.manifest)
        self.assertEqual(["publish_tree_allowlist_mismatch"], errors)
        self.assertNotIn("restricted-note", " ".join(errors))
        self.assertNotIn("synthetic-private-marker", " ".join(errors))

    def test_broken_link_fails_without_disclosing_target(self):
        (self.publish / "index.html").write_text('<a href="not-here.html">x</a>', encoding="utf-8")
        errors = checker.check_site(self.repo, self.manifest)
        self.assertIn("reference_missing_or_unlisted", errors)
        self.assertNotIn("not-here.html", " ".join(errors))

    def test_traversal_link_fails_without_disclosing_target(self):
        (self.publish / "index.html").write_text('<a href="../../restricted.html">x</a>', encoding="utf-8")
        errors = checker.check_site(self.repo, self.manifest)
        self.assertIn("reference_invalid", errors)
        self.assertNotIn("restricted.html", " ".join(errors))

    def test_absolute_local_link_is_resolved_inside_publish_root(self):
        (self.publish / "index.html").write_text('<a href="/about.html">About</a>', encoding="utf-8")
        self.assertEqual([], checker.check_site(self.repo, self.manifest))

    def test_parent_relative_link_inside_publish_root_is_allowed(self):
        nested = self.publish / "nested"
        nested.mkdir()
        (nested / "page.html").write_text('<a href="../about.html">About</a>', encoding="utf-8")
        self.write_manifest(["index.html", "about.html", "nested/page.html"])
        self.assertEqual([], checker.check_site(self.repo, self.manifest))

    def test_root_link_resolves_to_manifest_index(self):
        (self.publish / "index.html").write_text('<a href="/">Home</a>', encoding="utf-8")
        self.assertEqual([], checker.check_site(self.repo, self.manifest))

    def test_symlink_in_publish_tree_fails_closed(self):
        outside = self.repo / "outside.txt"
        outside.write_text("synthetic-private-marker", encoding="utf-8")
        try:
            (self.publish / "linked.txt").symlink_to(outside)
        except (OSError, NotImplementedError):
            self.skipTest("symlinks are not available in this environment")
        errors = checker.check_site(self.repo, self.manifest)
        self.assertEqual(["publish_tree_invalid"], errors)
        self.assertNotIn("synthetic-private-marker", " ".join(errors))


if __name__ == "__main__":
    unittest.main()
