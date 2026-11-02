import unittest
from datetime import date

import tests  # noqa: F401  (src を import パスに追加)
from weekly import aggregate_weekly, is_week_complete, iso_week_key

TH = -5.0


def by_week(weeks):
    return {w.week: w for w in weeks}


class AggregateTest(unittest.TestCase):
    def test_friday_holiday_uses_thursday(self):
        prices = [
            (date(2026, 10, 23), 100),  # 金
            (date(2026, 10, 28), 101),  # 水
            (date(2026, 10, 29), 102),  # 木（金曜は休みと仮定）
        ]
        w = by_week(aggregate_weekly(prices, date(2026, 11, 2), TH))["2026-W44"]
        self.assertEqual(w.date, date(2026, 10, 29))
        self.assertEqual(w.price, 102)
        self.assertEqual(w.prev_date, date(2026, 10, 23))

    def test_year_end_short_week(self):
        prices = [
            (date(2025, 12, 26), 39668),
            (date(2025, 12, 29), 39650),  # この週はこの1日だけ
            (date(2026, 1, 5), 39457),
            (date(2026, 1, 9), 39785),
        ]
        weeks = by_week(aggregate_weekly(prices, date(2026, 1, 10), TH))
        self.assertEqual(weeks["2026-W01"].date, date(2025, 12, 29))
        self.assertEqual(weeks["2026-W02"].prev_date, date(2025, 12, 29))

    def test_week_with_no_business_day_is_skipped(self):
        prices = [(date(2026, 10, 9), 100), (date(2026, 10, 23), 90)]  # W42 が丸ごと無い
        weeks = aggregate_weekly(prices, date(2026, 10, 24), TH)
        self.assertEqual([w.week for w in weeks], ["2026-W43", "2026-W41"])
        self.assertEqual(weeks[0].prev_date, date(2026, 10, 9))
        self.assertEqual(weeks[0].change_pct, -10.0)
        self.assertTrue(weeks[0].alert)

    def test_exactly_minus_5_is_alert(self):
        prices = [(date(2026, 10, 23), 40000), (date(2026, 10, 30), 38000)]
        w = aggregate_weekly(prices, date(2026, 10, 31), TH)[0]
        self.assertEqual(w.change_pct, -5.0)
        self.assertTrue(w.alert)

    def test_just_above_minus_5_is_not_alert(self):
        # 99951 / 105211 - 1 = -4.9995...% → 表示は -5.0 だがアラートにはならない
        prices = [(date(2026, 10, 23), 105211), (date(2026, 10, 30), 99951)]
        w = aggregate_weekly(prices, date(2026, 10, 31), TH)[0]
        self.assertEqual(w.change_pct, -5.0)
        self.assertFalse(w.alert)

    def test_single_row(self):
        w = aggregate_weekly([(date(2026, 10, 30), 100)], date(2026, 10, 31), TH)[0]
        self.assertIsNone(w.prev_price)
        self.assertIsNone(w.change_pct)
        self.assertFalse(w.alert)

    def test_iso_year_boundary(self):
        self.assertEqual(iso_week_key(date(2026, 12, 31)), "2026-W53")
        self.assertEqual(iso_week_key(date(2027, 1, 8)), "2027-W01")
        prices = [(date(2026, 12, 31), 100), (date(2027, 1, 8), 110)]
        w = aggregate_weekly(prices, date(2027, 1, 9), TH)[0]
        self.assertEqual(w.week, "2027-W01")
        self.assertEqual(w.prev_date, date(2026, 12, 31))
        self.assertEqual(w.change_pct, 10.0)

    def test_sorted_desc(self):
        prices = [(date(2026, 10, 16), 1), (date(2026, 10, 23), 2), (date(2026, 10, 30), 3)]
        weeks = aggregate_weekly(prices, date(2026, 10, 31), TH)
        self.assertEqual([w.week for w in weeks], ["2026-W44", "2026-W43", "2026-W42"])


class CompleteTest(unittest.TestCase):
    THU = date(2026, 10, 29)
    FRI = date(2026, 10, 30)

    def test_saturday_with_friday_data(self):
        self.assertTrue(is_week_complete(self.FRI, date(2026, 10, 31)))

    def test_saturday_with_thursday_data_is_partial(self):
        self.assertFalse(is_week_complete(self.THU, date(2026, 10, 31)))

    def test_next_monday_with_thursday_data(self):
        self.assertTrue(is_week_complete(self.THU, date(2026, 11, 2)))

    def test_midweek_is_partial(self):
        self.assertFalse(is_week_complete(date(2026, 10, 28), self.THU))

    def test_only_latest_week_can_be_partial(self):
        prices = [(date(2026, 10, 23), 100), (date(2026, 10, 28), 101)]
        weeks = aggregate_weekly(prices, date(2026, 10, 29), TH)
        self.assertTrue(weeks[0].is_partial)
        self.assertFalse(weeks[1].is_partial)


if __name__ == "__main__":
    unittest.main()
