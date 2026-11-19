"""Black-box CLI tests; runnable with unittest or pytest."""
from __future__ import annotations

import csv
import os
from pathlib import Path
import random
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
CANDIDATE = Path(os.environ.get("STOCK_TASK_CANDIDATE", ROOT / "reference" / "reconcile.py")).resolve()
IHEAD = ["sku", "opening_stock"]
RHEAD = ["event_id", "sku", "delta", "effective_at", "recorded_at", "status"]
CUTOFF = "2026-01-01T12:00:00Z"


class ReconciliationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="stock test ")
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.inventory = self.base / "inventory input.csv"
        self.revisions = self.base / "revision input.csv"
        self.output = self.base / "report output.csv"

    def write_csv(self, path, header, rows):
        with path.open("w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f, lineterminator="\n")
            writer.writerow(header)
            writer.writerows(rows)

    def run_case(self, stock, events, cutoff=CUTOFF):
        self.write_csv(self.inventory, IHEAD, stock)
        self.write_csv(self.revisions, RHEAD, events)
        return self.invoke(cutoff)

    def invoke(self, cutoff=CUTOFF, output=None):
        result = subprocess.run(
            [sys.executable, str(CANDIDATE), "--inventory", str(self.inventory),
             "--revisions", str(self.revisions), "--as-of", cutoff,
             "--output", str(output or self.output)],
            capture_output=True, text=True, timeout=10,
        )
        self.assertEqual(result.stdout, "")
        return result

    def assert_success(self, result, expected):
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.output.read_text(encoding="utf-8"), expected)

    def assert_invalid(self, result):
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertTrue(result.stderr.startswith("error:"), result.stderr)

    def test_published_example(self):
        self.inventory.write_bytes((ROOT / "examples" / "inventory.csv").read_bytes())
        self.revisions.write_bytes((ROOT / "examples" / "revisions.csv").read_bytes())
        result = self.invoke()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.output.read_bytes(), (ROOT / "examples" / "expected.csv").read_bytes())

    def test_empty_events_and_sorted_output(self):
        result = self.run_case([["z", "0"], ["A", "02"], ["a", "1"]], [])
        self.assert_success(result, "sku,opening_stock,net_change,closing_stock\nA,2,0,2\na,1,0,1\nz,0,0,0\n")
        self.assertNotIn(b"\r", self.output.read_bytes())

    def test_latest_revision_not_sum_of_revisions(self):
        events = [
            ["ev1", "x", "5", "2026-01-01T08:00:00Z", "2026-01-01T09:00:00Z", "posted"],
            ["ev1", "x", "-3", "2026-01-01T08:00:00Z", "2026-01-01T10:00:00Z", "posted"],
        ]
        self.assert_success(self.run_case([["x", "2"]], events), "sku,opening_stock,net_change,closing_stock\nx,2,-3,-1\n")

    def test_latest_void_suppresses_previous_posted_revision(self):
        events = [
            ["e", "x", "3", "2026-01-01T09:00:00Z", "2026-01-01T09:00:00Z", "posted"],
            ["e", "x", "0", "2026-01-01T09:00:00Z", "2026-01-01T10:00:00Z", "void"],
        ]
        self.assert_success(self.run_case([["x", "2"]], events), "sku,opening_stock,net_change,closing_stock\nx,2,0,2\n")

    def test_future_effective_latest_does_not_fall_back(self):
        events = [
            ["e", "x", "3", "2026-01-01T09:00:00Z", "2026-01-01T09:00:00Z", "posted"],
            ["e", "x", "5", "2026-01-01T12:00:01Z", "2026-01-01T10:00:00Z", "posted"],
        ]
        self.assert_success(self.run_case([["x", "2"]], events), "sku,opening_stock,net_change,closing_stock\nx,2,0,2\n")

    def test_future_recorded_revision_ignored(self):
        events = [
            ["e", "x", "3", "2026-01-01T09:00:00Z", "2026-01-01T09:00:00Z", "posted"],
            ["e", "x", "9", "2026-01-01T09:00:00Z", "2026-01-01T12:00:00.000001Z", "posted"],
        ]
        self.assert_success(self.run_case([["x", "2"]], events), "sku,opening_stock,net_change,closing_stock\nx,2,3,5\n")

    def test_offsets_and_cutoff_are_compared_as_instants(self):
        events = [
            ["a", "x", "2", "2026-01-01T14:00:00+02:00", "2026-01-01T07:00:00-05:00", "posted"],
            ["b", "x", "4", "2026-01-01T12:00:00.000001Z", "2026-01-01T12:00:00Z", "posted"],
        ]
        self.assert_success(self.run_case([["x", "5"]], events, "2026-01-01T15:00:00+03:00"), "sku,opening_stock,net_change,closing_stock\nx,5,2,7\n")

    def test_semantically_identical_latest_ties_are_accepted(self):
        events = [
            ["e", "x", "+3", "2026-01-01T09:00:00Z", "2026-01-01T10:00:00Z", "posted"],
            ["e", "x", "3", "2026-01-01T11:00:00+02:00", "2026-01-01T05:00:00-05:00", "posted"],
        ]
        self.assert_success(self.run_case([["x", "1"]], events), "sku,opening_stock,net_change,closing_stock\nx,1,3,4\n")

    def test_conflicting_latest_tie_preserves_existing_output(self):
        events = [
            ["e", "x", "3", "2026-01-01T09:00:00Z", "2026-01-01T10:00:00Z", "posted"],
            ["e", "x", "4", "2026-01-01T09:00:00Z", "2026-01-01T10:00:00Z", "posted"],
        ]
        self.output.write_text("do not replace\n", encoding="utf-8")
        self.assert_invalid(self.run_case([["x", "1"]], events))
        self.assertEqual(self.output.read_text(encoding="utf-8"), "do not replace\n")

    def test_earlier_conflict_may_be_superseded(self):
        events = [
            ["e", "x", "3", "2026-01-01T09:00:00Z", "2026-01-01T10:00:00Z", "posted"],
            ["e", "x", "4", "2026-01-01T09:00:00Z", "2026-01-01T10:00:00Z", "posted"],
            ["e", "x", "8", "2026-01-01T09:00:00Z", "2026-01-01T11:00:00Z", "posted"],
        ]
        self.assert_success(self.run_case([["x", "1"]], events), "sku,opening_stock,net_change,closing_stock\nx,1,8,9\n")

    def test_unknown_sku_only_errors_if_it_contributes(self):
        base = ["e", "missing", "3", "2026-01-01T09:00:00Z", "2026-01-01T10:00:00Z", "void"]
        self.assert_success(self.run_case([["x", "1"]], [base]), "sku,opening_stock,net_change,closing_stock\nx,1,0,1\n")
        base[-1] = "posted"
        self.assert_invalid(self.run_case([["x", "1"]], [base]))

    def test_invalid_values_are_rejected_even_after_cutoff(self):
        good = ["e", "x", "1", "2026-01-01T10:00:00Z", "2026-01-02T10:00:00Z", "posted"]
        changes = [(0, "bad id"), (2, "1.5"), (3, "2026-01-01T10:00:00"), (5, "POSTED")]
        for index, bad in changes:
            row = good.copy()
            row[index] = bad
            with self.subTest(index=index, bad=bad):
                self.assert_invalid(self.run_case([["x", "1"]], [row]))

    def test_bad_headers_duplicate_sku_and_missing_fields(self):
        self.write_csv(self.inventory, ["sku", "quantity"], [["x", "1"]])
        self.write_csv(self.revisions, RHEAD, [])
        self.assert_invalid(self.invoke())
        self.assert_invalid(self.run_case([["x", "1"], ["x", "2"]], []))
        self.assert_invalid(self.run_case([["x", "1"]], [["e", "x"]]))

    def test_output_cannot_replace_an_input(self):
        self.write_csv(self.inventory, IHEAD, [["x", "1"]])
        self.write_csv(self.revisions, RHEAD, [])
        before = self.inventory.read_bytes()
        self.assert_invalid(self.invoke(output=self.inventory))
        self.assertEqual(self.inventory.read_bytes(), before)

    def test_missing_required_arguments_have_contract_error(self):
        result = subprocess.run([sys.executable, str(CANDIDATE)], capture_output=True, text=True, timeout=10)
        self.assert_invalid(result)
        self.assertEqual(result.stdout, "")

    def test_seeded_case_is_independent_of_row_order(self):
        rng = random.Random(8154)
        stocks = [["alpha", "50"], ["beta", "40"], ["gamma", "30"]]
        totals = {"alpha": 0, "beta": 0, "gamma": 0}
        events = []
        for n in range(60):
            sku = stocks[n % len(stocks)][0]
            initial = rng.randint(-5, 5)
            final = rng.randint(-5, 5)
            events.extend([
                [f"id{n:03d}", sku, str(initial), "2026-01-01T10:00:00Z", "2026-01-01T08:00:00Z", "posted"],
                [f"id{n:03d}", sku, str(final), "2026-01-01T10:00:00Z", "2026-01-01T11:00:00Z", "posted"],
            ])
            totals[sku] += final
        expected = "sku,opening_stock,net_change,closing_stock\n" + "".join(
            f"{sku},{quantity},{totals[sku]},{int(quantity) + totals[sku]}\n" for sku, quantity in sorted(stocks)
        )
        rng.shuffle(events)
        self.assert_success(self.run_case(stocks, events), expected)
        rng.shuffle(events)
        self.assert_success(self.run_case(list(reversed(stocks)), events), expected)


if __name__ == "__main__":
    unittest.main()
