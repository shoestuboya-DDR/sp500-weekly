import unittest
from datetime import date, datetime, timedelta, timezone

import tests  # noqa: F401  (src を import パスに追加)
from notify import build_error_mail, decide_weekly_mail, should_send_error
from weekly import WeekPoint

JST = timezone(timedelta(hours=9))


def wp(week, change_pct, *, alert=False, partial=False):
    return WeekPoint(
        week=week,
        date=date(2026, 10, 30),
        price=38123,
        prev_date=date(2026, 10, 23),
        prev_price=40567,
        change_pct=change_pct,
        alert=alert,
        is_partial=partial,
    )


def decide(weeks, last, summary=True):
    return decide_weekly_mail(weeks, last, weekly_summary=summary, fund_name="F", site_url="https://x/")


class DecideTest(unittest.TestCase):
    def test_already_notified(self):
        self.assertEqual(decide([wp("2026-W44", 1.0)], "2026-W44"), (None, None))

    def test_normal_week(self):
        target, mail = decide([wp("2026-W44", 1.1)], "2026-W43")
        self.assertEqual(target.week, "2026-W44")
        self.assertTrue(mail.subject.startswith("[S&P500] 2026-W44 前週比 +1.10%"))
        self.assertIn("https://x/", mail.text)

    def test_normal_week_summary_off(self):
        target, mail = decide([wp("2026-W44", 1.1)], "2026-W43", summary=False)
        self.assertEqual(target.week, "2026-W44")  # 通知済みとして記録はする
        self.assertIsNone(mail)

    def test_alert_week(self):
        target, mail = decide([wp("2026-W44", -6.02, alert=True)], "2026-W43", summary=False)
        self.assertIn("【アラート】", mail.subject)
        self.assertIn("-6.02%", mail.subject)
        self.assertIn("font-weight:bold", mail.html)

    def test_partial_week_is_not_notified(self):
        weeks = [wp("2026-W45", -7.0, alert=True, partial=True), wp("2026-W44", 1.0)]
        target, mail = decide(weeks, "2026-W44")
        self.assertIsNone(target)
        self.assertIsNone(mail)

    def test_partial_skipped_and_previous_confirmed_notified(self):
        weeks = [wp("2026-W45", -7.0, alert=True, partial=True), wp("2026-W44", 1.0)]
        target, _ = decide(weeks, "2026-W43")
        self.assertEqual(target.week, "2026-W44")

    def test_first_run(self):
        target, mail = decide([wp("2026-W44", 1.0)], None)
        self.assertEqual(target.week, "2026-W44")
        self.assertIsNotNone(mail)

    def test_year_boundary_ordering(self):
        target, _ = decide([wp("2027-W01", 1.0)], "2026-W53")
        self.assertEqual(target.week, "2027-W01")


class ErrorTest(unittest.TestCase):
    NOW = datetime(2026, 11, 2, 9, 0, tzinfo=JST)

    def test_first_error(self):
        self.assertTrue(should_send_error(None, self.NOW))

    def test_within_24h(self):
        last = (self.NOW - timedelta(hours=23)).isoformat()
        self.assertFalse(should_send_error(last, self.NOW))

    def test_after_24h(self):
        last = (self.NOW - timedelta(hours=24)).isoformat()
        self.assertTrue(should_send_error(last, self.NOW))

    def test_error_mail(self):
        mail = build_error_mail("timeout <x>", "2026-10-30")
        self.assertIn("【エラー】", mail.subject)
        self.assertIn("&lt;x&gt;", mail.html)


if __name__ == "__main__":
    unittest.main()
