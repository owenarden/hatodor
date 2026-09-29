import unittest
from datetime import date, time

from clarifier.dates import pick_date

TERM = dict(term_start=date(2026, 8, 6), term_end=date(2026, 12, 31), today=date(2026, 9, 29))


def day(text, period):
    found = pick_date(text, period, **TERM)
    return found.day if found else None


class PickDateTests(unittest.TestCase):
    def test_period_in_title(self):
        t = "HOMEWORK - Reading - DUE: 10/6/2026 (Period 3) or 10/7/2026 (Period 2)"
        self.assertEqual(day(t, 3), date(2026, 10, 6))
        self.assertEqual(day(t, 2), date(2026, 10, 7))

    def test_year_typo_is_corrected(self):
        t = "DUE: 10/6/2026 (Period 3) or 10/7/2027 (Period 2)"
        self.assertEqual(day(t, 2), date(2026, 10, 7))

    def test_odd_even_blocks(self):
        t = "Unit 3 Test - 10/20/2026 (ODD BLOCKS) or 10/21/2026 (EVEN BLOCKS)"
        self.assertEqual(day(t, 3), date(2026, 10, 20))
        self.assertEqual(day(t, 4), date(2026, 10, 21))

    def test_month_names_with_ordinals(self):
        t = "DUE: September 15th (Odd Blocks) or September 16th (Even Blocks)"
        self.assertEqual(day(t, 1), date(2026, 9, 15))

    def test_block_lists_in_description(self):
        t = "<p>A quiz Tues 10/6 (Block 3) and Weds 10/7 (Blocks 2, 4 and 6).</p>"
        self.assertEqual(day(t, 2), date(2026, 10, 7))
        self.assertEqual(day(t, 3), date(2026, 10, 6))
        self.assertIsNone(day(t, 5))

    def test_per_abbreviation(self):
        t = "Due: Tues 10/6 (Per 3) and Weds 10/7 (Per 2, 4 and 6)"
        self.assertEqual(day(t, 4), date(2026, 10, 7))

    def test_all_blocks_and_single_due(self):
        self.assertEqual(day("Quiz - DUE: 8/17/2026 (All Blocks)", 3), date(2026, 8, 17))
        self.assertEqual(day("HOMEWORK - Reading - DUE: 9/28/2026", 3), date(2026, 9, 28))

    def test_rubric_fractions_are_not_dates(self):
        self.assertIsNone(day("Definition: 4/5, Examples: 4/5, Visuals 4.5/5", 3))

    def test_unqualified_pair_is_ambiguous(self):
        self.assertIsNone(day("Study Guide for Roots Quiz 10/6 and 10/7", 2))

    def test_semester_deadline_with_time(self):
        t = ("Critiques are due within one month. First semester due December 14th, "
             "3:30PM. Second semester due May 24th, 3:30PM")
        found = pick_date(t, 6, **TERM)
        self.assertEqual(found.day, date(2026, 12, 14))
        self.assertEqual(found.at, time(15, 30))


if __name__ == "__main__":
    unittest.main()
