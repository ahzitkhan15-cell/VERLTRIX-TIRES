"""Integration tests: run feed_fixer.py as a script against sample CSV files.

Unlike tests/test_feed_fixer.py, these tests never import the module. They run
`python3 feed_fixer.py ...` in a subprocess, so argument parsing, exit codes,
stdout/stderr and the CSV files written to disk are all exercised the way a
user runs the tool.
"""
import csv
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "feed_fixer.py"
FIXTURES = Path(__file__).resolve().parent / "fixtures"
SAMPLE_FIX_LIST = FIXTURES / "sample_fix_list.csv"
PRICES = FIXTURES / "sources" / "prices.csv"
IMAGES = FIXTURES / "sources" / "images.csv"


def run_fixer(*args, cwd=None):
    """Run the script with the given arguments and return the completed process."""
    return subprocess.run([sys.executable, str(SCRIPT), *map(str, args)],
                          cwd=str(cwd or REPO_ROOT), capture_output=True,
                          text=True, check=False)


def read_csv(path):
    """Read a CSV file into a list of dicts."""
    with open(path, newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_csv(path, header, rows):
    """Write rows to a CSV file."""
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=header)
        writer.writeheader()
        writer.writerows(rows)


class TemplateTests(unittest.TestCase):
    """The template command driven from the command line."""

    def test_template_from_sample(self):
        """Only failing rows are written, with just the columns they need."""
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "to_fill.csv"
            result = run_fixer("template", SAMPLE_FIX_LIST, "-o", out)
            self.assertEqual(result.returncode, 0, result.stderr)
            rows = read_csv(out)
            self.assertEqual(list(rows[0].keys()),
                             ["record_id", "title", "price", "availability",
                              "image_link", "link"])
            self.assertEqual([r["record_id"].strip() for r in rows],
                             ["VTX-100", "VTX-101", "VTX-102", "VTX-104", "VTX-105"])
            self.assertTrue(all(r["price"] == "" and r["link"] == "" for r in rows))
            self.assertIn("Wrote 5 rows", result.stdout)

    def test_template_with_nothing_failing(self):
        """A fix list whose rows all pass writes an empty sheet and exits 0."""
        with tempfile.TemporaryDirectory() as tmp:
            fix_list = Path(tmp) / "all_pass.csv"
            write_csv(fix_list, ["record_id", "title", "status", "failing_fields",
                                 "what_is_needed"],
                      [{"record_id": "VTX-1", "title": "T", "status": "PASS",
                        "failing_fields": "", "what_is_needed": ""}])
            out = Path(tmp) / "to_fill.csv"
            result = run_fixer("template", fix_list, "-o", out)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(out.read_text(encoding="utf-8").strip(),
                             "record_id,title")
            self.assertIn("No rows need filling", result.stdout)


class FixIntegrationTests(unittest.TestCase):
    """The fix command driven from the command line."""

    def test_sample_feed_and_report(self):
        """Sources are merged by alias, normalised, and remaining gaps reported."""
        with tempfile.TemporaryDirectory() as tmp:
            feed_out = Path(tmp) / "feed.csv"
            report_out = Path(tmp) / "report.csv"
            result = run_fixer("fix", SAMPLE_FIX_LIST, PRICES, IMAGES,
                               "--feed-out", feed_out, "--report-out", report_out)
            self.assertEqual(result.returncode, 1, result.stderr)  # gtin row still fails
            self.assertIn("5 PASS, 1 FAIL", result.stdout)
            self.assertIn("10 missing values filled", result.stdout)

            feed = {r["record_id"]: r for r in read_csv(feed_out)}
            self.assertEqual(feed["VTX-100"]["price"], "129.90 USD")
            self.assertEqual(feed["VTX-100"]["availability"], "in_stock")
            self.assertEqual(feed["VTX-102"]["price"], "1049.00 USD")
            self.assertEqual(feed["VTX-102"]["availability"], "out_of_stock")
            self.assertEqual(feed["VTX-102"]["image_link"],
                             "https://cdn.example.com/102.jpg")
            self.assertEqual(feed["VTX-102"]["link"],
                             "https://shop.example.com/p/102")
            self.assertEqual(feed["VTX-102"]["title"],
                             'ARDENT PROMIX, AP01 "225/45R18"')
            # A padded record_id is matched and written back trimmed.
            self.assertEqual(feed["VTX-105"]["availability"], "in_stock")
            self.assertEqual(feed["VTX-105"]["price"], "")

            report = {r["record_id"]: r for r in read_csv(report_out)}
            self.assertEqual(report["VTX-103"]["status"], "PASS")
            self.assertEqual(report["VTX-104"]["status"], "FAIL")
            self.assertEqual(report["VTX-104"]["failing_fields"], "gtin")
            self.assertIn("unknown field 'gtin'", report["VTX-104"]["what_is_needed"])

    def test_bad_values_are_reported_and_not_written(self):
        """Unusable values keep the cell blank so the live feed value survives."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            fix_list = tmp / "fix.csv"
            write_csv(fix_list, ["record_id", "title", "status", "failing_fields",
                                 "what_is_needed"],
                      [{"record_id": "VTX-200", "title": "Bad price", "status": "FAIL",
                        "failing_fields": "price", "what_is_needed": ""},
                       {"record_id": "VTX-201", "title": "Bad stock", "status": "FAIL",
                        "failing_fields": "availability", "what_is_needed": ""},
                       {"record_id": "VTX-202", "title": "Bad link", "status": "FAIL",
                        "failing_fields": "link", "what_is_needed": ""}])
            source = tmp / "source.csv"
            write_csv(source, ["record_id", "price", "availability", "link"],
                      [{"record_id": "VTX-200", "price": "call us",
                        "availability": "", "link": ""},
                       {"record_id": "VTX-201", "price": "", "availability": "maybe",
                        "link": ""},
                       {"record_id": "VTX-202", "price": "", "availability": "",
                        "link": "not a url"}])
            feed_out, report_out = tmp / "feed.csv", tmp / "report.csv"
            result = run_fixer("fix", fix_list, source, "--feed-out", feed_out,
                               "--report-out", report_out)
            self.assertEqual(result.returncode, 1, result.stderr)

            feed = {r["record_id"]: r for r in read_csv(feed_out)}
            self.assertEqual(feed["VTX-200"]["price"], "")
            self.assertEqual(feed["VTX-201"]["availability"], "")
            self.assertEqual(feed["VTX-202"]["link"], "")

            report = {r["record_id"]: r for r in read_csv(report_out)}
            self.assertTrue(all(r["status"] == "FAIL" for r in report.values()))
            self.assertIn("unreadable price 'call us'", report["VTX-200"]["what_is_needed"])
            self.assertIn("unknown availability 'maybe'",
                          report["VTX-201"]["what_is_needed"])
            self.assertIn("not a valid http(s) URL",
                          report["VTX-202"]["what_is_needed"])

    def test_later_source_wins_and_blanks_do_not_overwrite(self):
        """A later file overrides an earlier one; an empty cell never clears a value."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            fix_list = tmp / "fix.csv"
            write_csv(fix_list, ["record_id", "title", "status", "failing_fields",
                                 "what_is_needed"],
                      [{"record_id": "VTX-300", "title": "T", "status": "FAIL",
                        "failing_fields": "price", "what_is_needed": ""}])
            first, second, blank = tmp / "a.csv", tmp / "b.csv", tmp / "c.csv"
            write_csv(first, ["record_id", "price"],
                      [{"record_id": "VTX-300", "price": "10"}])
            write_csv(second, ["record_id", "price"],
                      [{"record_id": "VTX-300", "price": "12.5"}])
            write_csv(blank, ["record_id", "price"],
                      [{"record_id": "VTX-300", "price": ""}])
            feed_out, report_out = tmp / "feed.csv", tmp / "report.csv"
            result = run_fixer("fix", fix_list, first, second, blank,
                               "--feed-out", feed_out, "--report-out", report_out)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(read_csv(feed_out)[0]["price"], "12.50 USD")

    def test_require_all_flags_rows_without_a_source(self):
        """--require-all checks every field, so a previously passing row can fail."""
        with tempfile.TemporaryDirectory() as tmp:
            report_out = Path(tmp) / "report.csv"
            result = run_fixer("fix", SAMPLE_FIX_LIST, PRICES, IMAGES, "--require-all",
                               "--feed-out", Path(tmp) / "feed.csv",
                               "--report-out", report_out)
            self.assertEqual(result.returncode, 1, result.stderr)
            self.assertIn("1 PASS, 5 FAIL", result.stdout)
            report = {r["record_id"]: r for r in read_csv(report_out)}
            self.assertEqual(report["VTX-103"]["status"], "FAIL")
            self.assertEqual(report["VTX-102"]["status"], "PASS")

    def test_rerun_on_remaining_report_is_clean(self):
        """The report can be fed back in once every row is fixed."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            rows = [r for r in read_csv(SAMPLE_FIX_LIST) if r["record_id"].strip()
                    != "VTX-104"]
            fix_list = tmp / "fix.csv"
            write_csv(fix_list, list(rows[0].keys()), rows)
            first_feed, report = tmp / "feed1.csv", tmp / "report1.csv"
            first = run_fixer("fix", fix_list, PRICES, IMAGES,
                              "--feed-out", first_feed, "--report-out", report)
            self.assertEqual(first.returncode, 0, first.stderr)

            second_feed, second_report = tmp / "feed2.csv", tmp / "report2.csv"
            second = run_fixer("fix", report, PRICES, IMAGES,
                               "--feed-out", second_feed, "--report-out", second_report)
            self.assertEqual(second.returncode, 0, second.stderr)
            self.assertIn("5 PASS, 0 FAIL", second.stdout)

    def test_default_output_paths(self):
        """Without output flags the tool writes into ./out relative to the caller."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            fix_list = tmp / "fix.csv"
            write_csv(fix_list, ["record_id", "title", "status", "failing_fields",
                                 "what_is_needed"],
                      [{"record_id": "VTX-400", "title": "T", "status": "FAIL",
                        "failing_fields": "availability", "what_is_needed": ""}])
            source = tmp / "source.csv"
            write_csv(source, ["record_id", "availability"],
                      [{"record_id": "VTX-400", "availability": "0"}])
            result = run_fixer("fix", fix_list, source, cwd=tmp)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue((tmp / "out" / "feed_fixed.csv").is_file())
            self.assertTrue((tmp / "out" / "feed_fix_list_remaining.csv").is_file())


class FailureModeTests(unittest.TestCase):
    """Bad input is rejected with a clear message and a non-zero exit code."""

    def test_missing_fix_list_file(self):
        """A fix list that does not exist fails instead of writing empty output."""
        with tempfile.TemporaryDirectory() as tmp:
            result = run_fixer("template", Path(tmp) / "nope.csv", "-o",
                               Path(tmp) / "out.csv")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("No such file", result.stderr)

    def test_fix_list_missing_columns(self):
        """A fix list without failing_fields is rejected."""
        with tempfile.TemporaryDirectory() as tmp:
            fix_list = Path(tmp) / "bad.csv"
            write_csv(fix_list, ["record_id", "title"],
                      [{"record_id": "VTX-1", "title": "T"}])
            result = run_fixer("fix", fix_list, PRICES, "--feed-out",
                               Path(tmp) / "feed.csv")
            self.assertEqual(result.returncode, 1)
            self.assertIn("missing columns", result.stderr)
            self.assertIn("failing_fields", result.stderr)

    def test_source_without_record_id(self):
        """A source file that cannot be matched to rows is rejected."""
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "noid.csv"
            write_csv(source, ["price"], [{"price": "10"}])
            result = run_fixer("fix", SAMPLE_FIX_LIST, source,
                               "--feed-out", Path(tmp) / "feed.csv")
            self.assertEqual(result.returncode, 1)
            self.assertIn("no record_id column", result.stderr)

    def test_source_without_usable_columns(self):
        """A source with only a record_id has nothing to contribute."""
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "empty_cols.csv"
            write_csv(source, ["record_id"], [{"record_id": "VTX-100"}])
            result = run_fixer("fix", SAMPLE_FIX_LIST, source,
                               "--feed-out", Path(tmp) / "feed.csv")
            self.assertEqual(result.returncode, 1)
            self.assertIn("no usable columns", result.stderr)


if __name__ == "__main__":
    unittest.main()
