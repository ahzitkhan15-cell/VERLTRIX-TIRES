import csv
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import feed_fixer as ff  # noqa: E402

FIX_LIST = [
    {"record_id": "VTX-1", "title": "A 225/45R18", "status": "FAIL",
     "failing_fields": "price; availability", "what_is_needed": ""},
    {"record_id": "VTX-2", "title": "B 205/55R16", "status": "FAIL",
     "failing_fields": "price; availability; image_link", "what_is_needed": ""},
    {"record_id": "TL-3", "title": "C 275/40R20", "status": "FAIL",
     "failing_fields": "image_link; link", "what_is_needed": ""},
    {"record_id": "VTX-4", "title": "D 215/60R16", "status": "PASS",
     "failing_fields": "", "what_is_needed": ""},
]


class NormalizeTests(unittest.TestCase):
    def test_price(self):
        self.assertEqual(ff.normalize_price("129.9"), ("129.90 USD", None))
        self.assertEqual(ff.normalize_price("$1,049.00"), ("1049.00 USD", None))
        self.assertEqual(ff.normalize_price("99 cad")[0], "99.00 CAD")
        self.assertIsNotNone(ff.normalize_price("0")[1])
        self.assertIsNotNone(ff.normalize_price("call us")[1])
        self.assertEqual(ff.normalize_price("")[1], "missing")

    def test_availability(self):
        self.assertEqual(ff.normalize_availability("In Stock")[0], "in_stock")
        self.assertEqual(ff.normalize_availability("out_of_stock")[0], "out_of_stock")
        self.assertEqual(ff.normalize_availability("12")[0], "in_stock")
        self.assertEqual(ff.normalize_availability("0")[0], "out_of_stock")
        self.assertIsNotNone(ff.normalize_availability("maybe")[1])

    def test_url(self):
        self.assertIsNone(ff.normalize_url("https://x.com/a.jpg")[1])
        self.assertIsNotNone(ff.normalize_url("x.com/a.jpg")[1])


class FixTests(unittest.TestCase):
    def test_merge_and_report(self):
        sources = {
            "VTX-1": {"price": "150", "availability": "in stock"},
            "VTX-2": {"price": "99.5", "availability": "3"},  # image still missing
            "TL-3": {"image_link": "https://cdn/x.jpg", "link": "not a url"},
        }
        feed, report, stats = ff.fix(FIX_LIST, sources, "USD")
        by_id = {r["record_id"]: r for r in report}
        self.assertEqual(by_id["VTX-1"]["status"], "PASS")
        self.assertEqual(by_id["VTX-2"]["failing_fields"], "image_link")
        self.assertIn("Supply an image URL", by_id["VTX-2"]["what_is_needed"])
        self.assertEqual(by_id["TL-3"]["failing_fields"], "link")
        self.assertEqual(by_id["VTX-4"]["status"], "PASS")
        self.assertEqual(feed[0]["price"], "150.00 USD")
        self.assertEqual(stats["pass"], 2)
        self.assertEqual(stats["fail"], 2)
        self.assertEqual(stats["filled"], 5)

    def test_unmatched_and_require_all(self):
        _, report, stats = ff.fix(FIX_LIST, {}, "USD")
        self.assertEqual(stats["unmatched"], 3)
        self.assertEqual(report[3]["status"], "PASS")
        _, report, _ = ff.fix(FIX_LIST, {}, "USD", require_all=True)
        self.assertEqual(report[3]["status"], "FAIL")

    def test_template(self):
        header, rows = ff.make_template(FIX_LIST)
        self.assertEqual(header, ["record_id", "title", "price", "availability", "image_link", "link"])
        self.assertEqual([r["record_id"] for r in rows], ["VTX-1", "VTX-2", "TL-3"])


class CliTests(unittest.TestCase):
    def test_end_to_end_with_aliases_and_override(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            fix_list = d / "fix.csv"
            ff.write_csv(fix_list, list(FIX_LIST[0].keys()), FIX_LIST)
            prices = d / "prices.csv"
            prices.write_text("SKU,Selling_Price,Stock\nVTX-1,10,5\nVTX-2,20,0\n")
            override = d / "override.csv"
            override.write_text("id,price,image_url,url\nVTX-1,12.5,,\nVTX-2,,https://i/2.jpg,\n"
                                "TL-3,,https://i/3.jpg,https://shop/3\n")
            out_feed, out_rep = d / "feed.csv", d / "rep.csv"
            rc = ff.main(["fix", str(fix_list), str(prices), str(override),
                          "--feed-out", str(out_feed), "--report-out", str(out_rep)])
            self.assertEqual(rc, 0)
            feed = {r["record_id"]: r for r in csv.DictReader(open(out_feed))}
            self.assertEqual(feed["VTX-1"]["price"], "12.50 USD")
            self.assertEqual(feed["VTX-2"]["availability"], "out_of_stock")
            self.assertEqual(feed["TL-3"]["link"], "https://shop/3")


if __name__ == "__main__":
    unittest.main()
