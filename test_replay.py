from dataclasses import replace
from datetime import date
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from make_fixture import generate
from replay import Movement, backtest, factors, read_ledger, triangle


ROOT = Path(__file__).parent
FIXTURE = ROOT / "fixtures/illustrative_ledger.csv"


class ReplayTests(unittest.TestCase):
    def test_late_restatement_cannot_leak(self):
        original = Movement("a", 2018, "x", 2018, date(2018, 12, 1), 123)
        revision = replace(original, cents=500, published=date(2020, 1, 1))
        first = triangle([revision, original], date(2019, 12, 31), 3)
        last = triangle([revision, original], date(2020, 12, 31), 3)
        self.assertEqual(123, first[2018, "x"][0])
        self.assertEqual(500, last[2018, "x"][0])

    def test_no_skipping_a_missing_age(self):
        a = Movement("a", 2018, "x", 2018, date(2018, 12, 31), 100)
        c = Movement("c", 2018, "x", 2020, date(2020, 12, 31), 40)
        cutoff = date(2020, 12, 31)
        self.assertNotIn(2, triangle([a, c], cutoff, 3)[2018, "x"])
        b = Movement("b", 2018, "x", 2019, date(2019, 12, 31), 0)
        self.assertEqual(140, triangle([a, b, c], cutoff, 3)[2018, "x"][2])

    def test_segment_fallback_excludes_target_and_future(self):
        t = {(2015, "a"): {0: 100, 1: 130}, (2016, "b"): {0: 100, 1: 150},
             (2017, "a"): {0: 10, 1: 999}, (2018, "a"): {0: 10, 1: 999}}
        f, count, source = factors(t, 2017, "a", 0, 1, 2)[0]
        self.assertEqual(("7/5", 2, "pooled"), (str(f), count, source))

    def test_duplicate_version_fails(self):
        a = Movement("a", 2018, "x", 2018, date(2018, 12, 31), 100)
        with self.assertRaisesRegex(ValueError, "duplicate version"):
            triangle([a, a], date(2020, 12, 31), 3)

    def test_future_versions_do_not_change_results(self):
        ledger = read_ledger(FIXTURE)
        future = replace(ledger[0], cents=999999999, published=date(2028, 1, 1))
        self.assertEqual(backtest(ledger), backtest([future, *ledger]))

    def test_fixture_repeatability(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "fixture.csv"
            generate(p)
            self.assertEqual(FIXTURE.read_bytes(), p.read_bytes())

    def test_cli_report(self):
        r = json.loads(subprocess.check_output([sys.executable, "replay.py"], cwd=ROOT, text=True))
        self.assertGreater(r["case_count"], 20)
        self.assertTrue(any(x["reason"] == "label not mature" for x in r["excluded"]))
        self.assertLess(r["metrics"]["prior_cohort_development"]["mean_absolute_error_cents"],
                        r["metrics"]["paid_to_date_baseline"]["mean_absolute_error_cents"])
        self.assertEqual(r["case_count"], sum(x["n"] for x in r["metrics_by_age"].values()))


if __name__ == "__main__":
    unittest.main()
