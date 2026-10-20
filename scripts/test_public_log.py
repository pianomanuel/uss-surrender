import unittest
from check_public_log import format_findings, scan_text


class PublicLogScannerTests(unittest.TestCase):
    def test_public_safe_log_passes(self):
        self.assertEqual(
            scan_text("# Public Development Log\n\nStatic-site validation is under review.\n"),
            [],
        )

    def test_findings_output_is_category_only(self):
        self.assertEqual(
            format_findings([(7, "example category")]),
            ["Public log check failed:", "- line 7: example category"],
        )


if __name__ == "__main__":
    unittest.main()
